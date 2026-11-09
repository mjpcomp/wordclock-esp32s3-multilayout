from pathlib import Path
import hashlib
import importlib.util
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "745fce049b70ca1fc0a2b109e1f12fd934ccc90b8016852ec7617b088b86944b"
RUNTIME_INCLUDES = '#include "BrightnessRuntimeStatusProtocol.h"\n#include "BrightnessScheduleRendererBinding.h"\n#include "LedStripInterface.h"\nextern LedStripInterface *activeLedStrip;\n'
PROVIDER = 'brightnessRuntimeStatusProtocol::State readBrightnessRuntime(void *) {\n    namespace status = brightnessRuntimeStatusProtocol;\n    status::State state = {};\n    state.observation = brightnessScheduleRuntimeOwner::applicationRuntime().observation(millis());\n    state.backend = !activeLedStrip ? status::BackendKind::None :\n        activeLedStrip->isVirtual() ? status::BackendKind::Virtual : status::BackendKind::Physical;\n    state.cacheCompiled = WORDCLOCK_ENABLE_RENDERER_CACHE != 0;\n    state.outputCompiled = WORDCLOCK_ENABLE_SCHEDULE_OUTPUT != 0;\n#if WORDCLOCK_ENABLE_RENDERER_CACHE\n    state.rendererAttached = activeLedStrip && brightnessScheduleBinding::application().ready(activeLedStrip);\n#endif\n    return state;\n}\n\n'
RUNTIME_PREFIX = '    const auto runtime = brightnessRuntimeStatusProtocol::handle(\n        data, size, reply, capacity, used, readBrightnessRuntime, nullptr);\n    if (runtime != brightnessRuntimeStatusProtocol::Result::NotRuntime)\n        return runtime == brightnessRuntimeStatusProtocol::Result::Handled;\n'

def normalize_adapter(text):
    for chunk in (RUNTIME_INCLUDES, PROVIDER, RUNTIME_PREFIX):
        if text.count(chunk) != 1:
            raise ValueError("Runtime extension missing, duplicated or changed")
        text = text.replace(chunk, "", 1)
    if hashlib.sha256(text.encode()).hexdigest() != BASE_SHA:
        raise ValueError("Unexpected adapter baseline outside approved extension")
    return text

def check(root):
    adapter = (root / 'src/WebPageAdapter.cpp').read_text()
    base = normalize_adapter(adapter)
    spec = importlib.util.spec_from_file_location('transport_contract', root / 'tests/test_brightness_schedule_transport.py')
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    transport.review(base)
    assert transport.prepared(adapter) == adapter
    assert transport.prepared(transport.prepared(adapter)) == adapter
    for chunk in (RUNTIME_INCLUDES, PROVIDER, RUNTIME_PREFIX):
        for bad in (adapter.replace(chunk, '', 1), adapter.replace(chunk, chunk + chunk, 1), adapter.replace(chunk, chunk + ' ', 1)):
            try:
                normalize_adapter(bad)
            except ValueError:
                pass
            else:
                raise AssertionError('Altered runtime extension passed guard')
    try:
        normalize_adapter(adapter + '\n')
    except ValueError:
        pass
    else:
        raise AssertionError('Unapproved base byte passed guard')
    script = (root / 'webpage/script.js').read_text()
    html = (root / 'webpage/index.html').read_text()
    module = (root / 'webpage/schedule-runtime-status.js').read_text()
    assert 'data.command === "brightness-schedule" || data.command === "brightness-runtime"' in script
    assert script.index('\tinitSchedulePage();') < script.index('\tinitRuntimeStatusPage();') < script.index('\tinitWebsocket();', script.index('\tinitRuntimeStatusPage();'))
    assert script.count('runtimeStatusPage.attach(socket)') == 1
    assert html.count('id="schedule-runtime-status"') == 1
    assert html.index('./schedule-runtime-status.js') < html.index('./script.js')
    assert 'global.createWordclockRuntimeStatus = create' in module
    for forbidden in ('new WebSocket', 'setInterval', '.close(', 'console.', 'innerHTML', 'sendCmd(', 'scheduleBridge', 'readMirc0PreviewSchedule'):
        assert forbidden not in module, forbidden
    assert module.count('socket.send(') == 1
    assert 'let debug = false;' in script and '\tdebug = false;' in script
    assert 'console.log(message);' in script
    binding = (root / 'include/BrightnessScheduleRendererBinding.h').read_text()
    for gate in ('RENDERER_CACHE', 'SCHEDULE_OUTPUT'):
        assert '#define WORDCLOCK_ENABLE_' + gate + ' 0' in binding
    for forbidden in ('.begin(', '.store(', '.service', '.show(', '.repaint(', '.adoptGain(', '.retire(', '.attach(', 'systemLocalTime', 'gettimeofday'):
        assert forbidden not in PROVIDER, forbidden
    for forbidden in ('store_.load', 'store_.save', 'store_.reset', 'gettimeofday', 'settimeofday'):
        assert forbidden not in module
    if '--packaged' in sys.argv:
        generated = root / '.pio/build/webpage/index.html'
        text = generated.read_text()
        assert 'createWordclockRuntimeStatus' in text and 'brightness-runtime' in text
        assert 'schedule-runtime-status' in text
        assert 'src="./schedule-runtime-status.js"' not in text

if __name__ == '__main__':
    check(ROOT)
    print('PASS: exact adapter extension, source contracts and requested packaging checks')
