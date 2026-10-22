#pragma once
#include "BrightnessSchedule.h"
#include <stddef.h>
#include <string.h>
#if defined(ESP32)
#include <nvs.h>
#endif

namespace brightnessScheduleStorage {
constexpr size_t MIN_BYTES = 16;
constexpr size_t MAX_BYTES = MIN_BYTES + 6 * brightnessSchedule::MAX_EVENTS;
struct Record {
    uint32_t revision;
    brightnessSchedule::Schedule schedule;
};
enum class Result {
    Ok, Missing, ResetRequired, ReadFailed, InvalidInput, Conflict,
    RevisionExhausted, WriteUncertain, ReadbackUncertain
};
enum class ReadResult { Ok, Missing, Invalid, Failed };
// CRC detects accidental corruption; it does not authenticate exported secrets.
inline uint32_t crc32(const uint8_t *data, size_t size) {
    uint32_t crc = 0xffffffffUL;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320UL : 0);
    }
    return crc ^ 0xffffffffUL;
}
inline void put16(uint8_t *p, uint16_t v) { p[0] = v & 255; p[1] = v >> 8; }
inline uint16_t get16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline void put32(uint8_t *p, uint32_t v) {
    for (uint8_t i = 0; i < 4; ++i) p[i] = (v >> (8 * i)) & 255;
}
inline uint32_t get32(const uint8_t *p) {
    uint32_t value = 0;
    for (uint8_t i = 0; i < 4; ++i) value |= uint32_t(p[i]) << (8 * i);
    return value;
}
inline bool encode(const Record &r, uint8_t *data, size_t capacity, size_t &size) {
    if (!data || !r.revision || !brightnessSchedule::valid(r.schedule)) return false;
    const size_t needed = MIN_BYTES + 6 * r.schedule.count;
    if (capacity < needed) return false;
    memcpy(data, "WCBS", 4);
    data[4] = 1;
    data[5] = r.schedule.count;
    put16(data + 6, r.schedule.defaultTenths);
    put32(data + 8, r.revision);
    for (uint8_t i = 0; i < r.schedule.count; ++i) {
        const brightnessSchedule::Event &e = r.schedule.events[i];
        uint8_t *p = data + 12 + 6 * i;
        put16(p, e.minute); put16(p + 2, e.targetTenths); put16(p + 4, e.fadeMinutes);
    }
    put32(data + needed - 4, crc32(data, needed - 4));
    size = needed;
    return true;
}
inline Result decode(const uint8_t *data, size_t size, Record &out) {
    if (!data || size < MIN_BYTES || size > MAX_BYTES) return Result::ResetRequired;
    if (memcmp(data, "WCBS", 4) || data[4] != 1) return Result::ResetRequired;
    const uint8_t count = data[5];
    if (count > brightnessSchedule::MAX_EVENTS || size != MIN_BYTES + 6 * count)
        return Result::ResetRequired;
    if (get32(data + size - 4) != crc32(data, size - 4)) return Result::ResetRequired;
    Record candidate = {};
    candidate.revision = get32(data + 8);
    candidate.schedule.defaultTenths = get16(data + 6);
    candidate.schedule.count = count;
    for (uint8_t i = 0; i < count; ++i) {
        const uint8_t *p = data + 12 + 6 * i;
        candidate.schedule.events[i] = {get16(p), get16(p + 2), get16(p + 4)};
    }
    if (!candidate.revision || !brightnessSchedule::valid(candidate.schedule))
        return Result::ResetRequired;
    out = candidate;
    return Result::Ok;
}
class Backend {
public:
    virtual ~Backend() = default;
    virtual ReadResult read(uint8_t *data, size_t capacity, size_t &size) = 0;
    // False means the outcome may be uncertain, not proof that flash is unchanged.
    virtual bool write(const uint8_t *data, size_t size) = 0;
};
// Observer callbacks run synchronously after a public operation; do not reenter Store.
using Observer = void (*)(Result, const Record *, void *);
// Use from one serialized sketch/event-loop context; revision checks are not a mutex.
class Store {
    Backend &backend;
    Observer observer_;
    void *context_;
    void notify(Result result, const Record &out) {
        if (observer_) observer_(result, result == Result::Ok ? &out : nullptr, context_);
    }
    Result loadRaw(Record &out) {
        uint8_t data[MAX_BYTES] = {};
        size_t size = 0;
        const ReadResult read = backend.read(data, sizeof(data), size);
        if (read == ReadResult::Missing) return Result::Missing;
        if (read == ReadResult::Invalid) return Result::ResetRequired;
        if (read != ReadResult::Ok) return Result::ReadFailed;
        return decode(data, size, out);
    }
    Result persist(const Record &candidate, Record &out) {
        uint8_t expected[MAX_BYTES] = {};
        size_t expectedSize = 0;
        if (!encode(candidate, expected, sizeof(expected), expectedSize)) return Result::InvalidInput;
        if (!backend.write(expected, expectedSize)) return Result::WriteUncertain;
        Record readback = {};
        if (loadRaw(readback) != Result::Ok) return Result::ReadbackUncertain;
        uint8_t actual[MAX_BYTES] = {};
        size_t actualSize = 0;
        if (!encode(readback, actual, sizeof(actual), actualSize) || actualSize != expectedSize ||
            memcmp(actual, expected, expectedSize)) return Result::ReadbackUncertain;
        out = readback;
        return Result::Ok;
    }
    Result replace(uint32_t expectedRevision, const brightnessSchedule::Schedule &schedule,
                   bool explicitReset, Record &out) {
        if (!brightnessSchedule::valid(schedule)) return Result::InvalidInput;
        Record current = {};
        const Result loaded = loadRaw(current);
        if (loaded == Result::ReadFailed) return loaded;
        if (loaded == Result::ResetRequired && !explicitReset) return loaded;
        const uint32_t revision = loaded == Result::Ok ? current.revision : 0;
        if (expectedRevision != revision) return Result::Conflict;
        if (revision == 0xffffffffUL) return Result::RevisionExhausted;
        Record candidate = {};
        candidate.revision = revision + 1;
        candidate.schedule = schedule;
        return persist(candidate, out);
    }
public:
    explicit Store(Backend &value, Observer observer = nullptr, void *context = nullptr)
        : backend(value), observer_(observer), context_(context) {}
    Result load(Record &out) {
        const Result result = loadRaw(out);
        notify(result, out);
        return result;
    }
    Result save(uint32_t expectedRevision, const brightnessSchedule::Schedule &schedule, Record &out) {
        const Result result = replace(expectedRevision, schedule, false, out);
        notify(result, out);
        return result;
    }
    // Explicit caller action only: no boot/read path invokes this automatically.
    Result reset(uint32_t expectedRevision, Record &out) {
        brightnessSchedule::Schedule fresh = {};
        fresh.defaultTenths = 1000;
        const Result result = replace(expectedRevision, fresh, true, out);
        notify(result, out);
        return result;
    }
};
#if defined(ESP32)
// No constructor I/O. Uses only wc-bright/schedule; never initializes or erases NVS.
class NvsBackend : public Backend {
public:
    ReadResult read(uint8_t *data, size_t capacity, size_t &size) override {
        size = 0;
        if (!data) return ReadResult::Failed;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-bright", NVS_READONLY, &handle);
        if (error == ESP_ERR_NVS_NOT_FOUND) return ReadResult::Missing;
        if (error != ESP_OK) return ReadResult::Failed;
        size_t needed = 0;
        error = nvs_get_blob(handle, "schedule", nullptr, &needed);
        if (error == ESP_ERR_NVS_NOT_FOUND) { nvs_close(handle); return ReadResult::Missing; }
        if (error == ESP_ERR_NVS_TYPE_MISMATCH) { nvs_close(handle); return ReadResult::Invalid; }
        if (error != ESP_OK) { nvs_close(handle); return ReadResult::Failed; }
        if (needed < MIN_BYTES || needed > MAX_BYTES || needed > capacity) {
            nvs_close(handle); return ReadResult::Invalid;
        }
        size = needed;
        error = nvs_get_blob(handle, "schedule", data, &size);
        nvs_close(handle);
        return error == ESP_OK && size == needed ? ReadResult::Ok : ReadResult::Failed;
    }
    bool write(const uint8_t *data, size_t size) override {
        if (!data || size < MIN_BYTES || size > MAX_BYTES) return false;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-bright", NVS_READWRITE, &handle);
        if (error != ESP_OK) return false;
        error = nvs_set_blob(handle, "schedule", data, size);
        if (error == ESP_OK) error = nvs_commit(handle);
        nvs_close(handle);
        return error == ESP_OK;
    }
};
#endif
} // namespace brightnessScheduleStorage
