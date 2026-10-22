#!/usr/bin/env python3
"""Test transport and review/stage exact adapter wiring; staging is explicit CI-only preparation."""
from pathlib import Path
import argparse
import hashlib
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
INPUT_SHA = 'fd98b0fa8830d39a64afeac9e20f98f01379b5b530cdbfa8eae9b272656ce53c'
CURRENT_SHA = '08767ab42205e8921596864008340f022958a353bef6758c460f1b1b59745151'
OUTPUT_SHA = '745fce049b70ca1fc0a2b109e1f12fd934ccc90b8016852ec7617b088b86944b'
BRIDGE = r'''#if defined(ESP32)
// Brightness schedule transport integration; one serialized event-loop context.
bool invokeBrightnessSchedule(const uint8_t *data, size_t size, char *reply,
                              size_t capacity, size_t &used, void *) {
    auto &store = brightnessScheduleRuntimeOwner::applicationRuntime().store();
    return brightnessScheduleProtocol::handle(store, data, size, reply, capacity, used);
}

bool sendBrightnessScheduleReply(uint8_t client, const char *data, size_t size, void *) {
    return webSocket.sendTXT(client, data, size);
}

bool routeBrightnessSchedule(uint8_t client, WStype_t type, uint8_t *data, size_t size) {
    namespace transport = brightnessScheduleTransport;
    static_assert(transport::kReplyBytes == brightnessScheduleProtocol::MIN_OUTPUT, "reply budget mismatch");
    static_assert(transport::kMaxTextBytes == brightnessScheduleProtocol::kMaxInput, "input budget mismatch");
    transport::Frame frame = transport::Frame::Other;
    if (type == WStype_TEXT) frame = transport::Frame::Text;
    else if (type == WStype_FRAGMENT_TEXT_START || type == WStype_FRAGMENT_BIN_START ||
             type == WStype_FRAGMENT || type == WStype_FRAGMENT_FIN) frame = transport::Frame::Fragment;
    static char reply[transport::kReplyBytes];
    const transport::Result result = transport::dispatch(frame, client, data, size, reply, sizeof(reply),
                                                        invokeBrightnessSchedule, sendBrightnessScheduleReply, nullptr);
    if (result == transport::Result::ReplyFailed)
        Serial.printf("[%u] Scheduler reply not delivered; reload required\n", static_cast<unsigned>(client));
    return result != transport::Result::PassThrough;
}
#endif

'''
PATCHES = [
    ('#include <Arduino.h>\n', '#include <Arduino.h>\n#if defined(ESP32)\n#include "BrightnessScheduleProtocol.h"\n#include "BrightnessScheduleTransport.h"\n#include "BrightnessScheduleRuntimeOwner.h"\n#endif\n'),
    ('\n} // namespace\n\n//------------------------------------------------------------------------------\n\nvoid webSocketEvent', '\n' + BRIDGE + '} // namespace\n\n//------------------------------------------------------------------------------\n\nvoid webSocketEvent'),
    ('    payload = (payload == NULL) ? (uint8_t *)"" : payload;\n    Serial.printf("Client-Nr.: [%u]  WStype: %u payload: %s\\n", num, type,\n                  payload);', '#if defined(ESP32)\n    if (routeBrightnessSchedule(num, type, payload, length)) return;\n#endif\n    payload = (payload == NULL) ? (uint8_t *)"" : payload;\n    Serial.printf("Client-Nr.: [%u] WStype: %u bytes: %u\\n", static_cast<unsigned>(num),\n                  static_cast<unsigned>(type), static_cast<unsigned>(length));'),
    ('        Serial.printf("[%u] Connected from %d.%d.%d.%d url: %s\\n", num, ip[0],\n                      ip[1], ip[2], ip[3], payload);', '        Serial.printf("[%u] Connected from %d.%d.%d.%d\\n", num, ip[0],\n                      ip[1], ip[2], ip[3]);'),
    ('        Serial.printf("[%u] get Text: %s\\n", length, payload);', '        Serial.printf("[%u] Text bytes: %u\\n", static_cast<unsigned>(num), static_cast<unsigned>(length));')
]
def review(text):
    if text.count(BRIDGE) != 1:
        raise SystemExit('Unexpected transport bridge; inspect before continuing')
    event = text.index('void webSocketEvent(')
    route = text.index('if (routeBrightnessSchedule(num, type, payload, length)) return;', event)
    if route >= text.index('uint8_t command = split(payload, 0);', event):
        raise SystemExit('Scheduler routing must precede numeric command parsing')
    if route >= text.index('payload = (payload == NULL)', event):
        raise SystemExit('Route the original explicit pointer/length before legacy normalization')
    if 'payload: %s' in text or 'get Text: %s' in text or 'url: %s' in text:
        raise SystemExit('Raw frame/URL logging must not expose transfer data')

def prepared(text):
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest == OUTPUT_SHA:
        review(text)
        return text
    if digest == CURRENT_SHA:
        old = ('    static brightnessScheduleStorage::NvsBackend backend;\n'
               '    static brightnessScheduleStorage::Store store(backend);')
        new = '    auto &store = brightnessScheduleRuntimeOwner::applicationRuntime().store();'
        include = '#include "BrightnessScheduleTransport.h"\n'
        if text.count(old) != 1 or text.count(include) != 1:
            raise SystemExit('Unexpected shared-owner upgrade anchors')
        text = text.replace(old, new, 1).replace(include, include + '#include "BrightnessScheduleRuntimeOwner.h"\n', 1)
    elif digest == INPUT_SHA:
        for old, new in PATCHES:
            if text.count(old) != 1:
                raise SystemExit('Missing/repeated adapter wiring anchor')
            text = text.replace(old, new, 1)
    else:
        raise SystemExit('Unexpected adapter baseline; inspect rather than guessing a patch')
    if hashlib.sha256(text.encode()).hexdigest() != OUTPUT_SHA:
        raise SystemExit('Unexpected adapter wiring output')
    review(text)
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage-adapter', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'src/WebPageAdapter.cpp'
    current = path.read_text()
    candidate = prepared(current)
    compiler = shutil.which('g++')
    if not compiler:
        raise SystemExit('g++ required for transport tests')
    with tempfile.TemporaryDirectory() as folder:
        binary = Path(folder) / 'transport'
        subprocess.run([compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'include'), str(ROOT / 'tests/brightness_schedule_transport_test.cpp'),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    if args.stage_adapter and candidate != current:
        path.write_text(candidate)
        print('Staged reviewed adapter for CI compile only; not committed or flashed')
    print('PASS: transport routing and reviewed adapter integration contract')
if __name__ == '__main__':
    main()
