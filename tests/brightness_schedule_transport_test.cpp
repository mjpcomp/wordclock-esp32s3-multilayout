#include "BrightnessScheduleTransport.h"
#include <assert.h>
#include <string>
#include <vector>
using namespace brightnessScheduleTransport;
struct Test {
    unsigned handles = 0, sends = 0;
    uint8_t client = 0;
    bool handlerOk = true, senderOk = true;
    size_t claimed = 2;
    const uint8_t *input = nullptr;
    size_t inputSize = 0;
    std::string reply;
};
static bool handler(const uint8_t *p, size_t n, char *out, size_t cap, size_t &used, void *context) {
    Test &t = *static_cast<Test *>(context);
    ++t.handles; t.input = p; t.inputSize = n;
    assert(cap >= kReplyBytes);
    out[0] = 'O'; out[1] = 'K'; used = t.claimed;
    return t.handlerOk;
}
static bool sender(uint8_t client, const char *p, size_t n, void *context) {
    Test &t = *static_cast<Test *>(context);
    ++t.sends; t.client = client; t.reply.assign(p, n); return t.senderOk;
}
static Result route(Frame kind, const uint8_t *p, size_t n, Test &t) {
    char out[kReplyBytes];
    return dispatch(kind, 7, p, n, out, sizeof(out), handler, sender, &t);
}
int main() {
    const uint8_t legacy[] = {'2','0','1'};
    Test t;
    assert(route(Frame::Text, legacy, sizeof(legacy), t) == Result::PassThrough && !t.handles && !t.sends);
    const uint8_t textCommand[] = {'0','9','7','t','i','m','e'};
    assert(route(Frame::Text, textCommand, sizeof(textCommand), t) == Result::PassThrough && !t.handles);
    const uint8_t json[] = {'{','}'};
    assert(route(Frame::Text, json, sizeof(json), t) == Result::Handled);
    assert(t.handles == 1 && t.sends == 1 && t.client == 7 && t.reply == "OK");
    assert(t.input == json && t.inputSize == 2);
    Test shortText;
    assert(route(Frame::Text, legacy, 2, shortText) == Result::Handled && shortText.handles == 1);
    Test nullText;
    assert(route(Frame::Text, nullptr, 0, nullText) == Result::Handled && nullText.handles == 1);
    Test other;
    assert(route(Frame::Other, nullptr, 99999, other) == Result::PassThrough && !other.handles && !other.sends);
    Test fragment;
    assert(route(Frame::Fragment, nullptr, 99999, fragment) == Result::Handled && !fragment.handles);
    assert(fragment.reply.find("complete-text-frame-required") != std::string::npos && fragment.client == 7);
    std::vector<uint8_t> oversized(kMaxTextBytes + 1, '2');
    Test large;
    assert(route(Frame::Text, oversized.data(), oversized.size(), large) == Result::Handled && !large.handles);
    assert(large.reply.find("frame-too-large") != std::string::npos);
    Test lost; lost.senderOk = false;
    assert(route(Frame::Text, json, 2, lost) == Result::ReplyFailed && lost.handles == 1 && lost.sends == 1);
    Test uncertain; uncertain.handlerOk = false;
    assert(route(Frame::Text, json, 2, uncertain) == Result::Handled && uncertain.handles == 1);
    assert(uncertain.reply.find("reply-unavailable") != std::string::npos && uncertain.reply.find("reloadRequired") != std::string::npos);
    for (size_t bad : {size_t(0), kReplyBytes, kReplyBytes + 1}) {
        Test invalid; invalid.claimed = bad;
        assert(route(Frame::Text, json, 2, invalid) == Result::Handled);
        assert(invalid.reply.find("reply-unavailable") != std::string::npos);
    }
    char small[1]; Test capacity;
    assert(dispatch(Frame::Text, 7, json, 2, small, sizeof(small), handler, sender, &capacity) == Result::Handled);
    assert(!capacity.handles && capacity.reply.find("reply-unavailable") != std::string::npos);
    Test noSender; char buffer[kReplyBytes];
    assert(dispatch(Frame::Text, 7, json, 2, buffer, sizeof(buffer), handler, nullptr, &noSender) == Result::ReplyFailed);
    assert(!noSender.handles && !noSender.sends);
    Test noHandler;
    assert(dispatch(Frame::Text, 7, json, 2, buffer, sizeof(buffer), nullptr, sender, &noHandler) == Result::Handled);
    assert(!noHandler.handles && noHandler.reply.find("reloadRequired") != std::string::npos);
    return 0;
}
