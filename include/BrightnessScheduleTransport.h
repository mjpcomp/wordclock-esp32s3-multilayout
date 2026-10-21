#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace brightnessScheduleTransport {
constexpr size_t kMaxTextBytes = 2048;
constexpr size_t kReplyBytes = 2048;
enum class Frame { Text, Fragment, Other };
enum class Result { PassThrough, Handled, ReplyFailed };
using Handler = bool (*)(const uint8_t *, size_t, char *, size_t, size_t &, void *);
using Sender = bool (*)(uint8_t, const char *, size_t, void *);
inline bool legacyPrefix(const uint8_t *data, size_t size) {
    if (!data || size < 3) return false;
    for (uint8_t i = 0; i < 3; ++i) if (data[i] < '0' || data[i] > '9') return false;
    return true;
}
inline Result fixedReply(uint8_t client, const char *reply, Sender send, void *context) {
    return send && send(client, reply, strlen(reply), context) ? Result::Handled : Result::ReplyFailed;
}
// Complete text frames only. No logging, GPIO, storage, retries or broadcasting here.
inline Result dispatch(Frame frame, uint8_t client, const uint8_t *data, size_t size,
                       char *reply, size_t capacity, Handler handle, Sender send, void *context) {
    if (frame == Frame::Other) return Result::PassThrough;
    if (frame == Frame::Text && size <= kMaxTextBytes && legacyPrefix(data, size)) return Result::PassThrough;
    if (!send) return Result::ReplyFailed;
    if (frame == Frame::Fragment)
        return fixedReply(client, "{\"command\":\"brightness-schedule\",\"schema\":1,\"requestId\":null,\"status\":\"complete-text-frame-required\"}", send, context);
    if (size > kMaxTextBytes)
        return fixedReply(client, "{\"command\":\"brightness-schedule\",\"schema\":1,\"requestId\":null,\"status\":\"frame-too-large\"}", send, context);
    size_t used = 0;
    if (!handle || !reply || capacity < kReplyBytes || !handle(data, size, reply, capacity, used, context) ||
        !used || used >= capacity || used >= kReplyBytes)
        return fixedReply(client, "{\"command\":\"brightness-schedule\",\"schema\":1,\"requestId\":null,\"status\":\"reply-unavailable\",\"reloadRequired\":true}", send, context);
    return send(client, reply, used, context) ? Result::Handled : Result::ReplyFailed;
}
} // namespace brightnessScheduleTransport
