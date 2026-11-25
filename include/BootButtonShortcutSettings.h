#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace bootButtonShortcut {
constexpr size_t kBytes = 16;
struct Record { uint32_t revision; bool enabled; };
inline uint32_t get32(const uint8_t *p) {
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 |
           uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
inline void put32(uint8_t *p, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) p[i] = uint8_t(value >> (8 * i));
}
// Corruption detection, not authentication.
inline uint32_t checksum(const uint8_t *data, size_t size) {
    uint32_t value = 2166136261UL;
    for (size_t i = 0; i < size; ++i) value = (value ^ data[i]) * 16777619UL;
    return value;
}
inline bool encode(const Record &record, uint8_t *data, size_t capacity) {
    if (!data || capacity < kBytes || !record.revision) return false;
    const uint8_t prefix[8] = {'B', 'O', 'O', 'T', 1, uint8_t(record.enabled), 0, 0};
    memcpy(data, prefix, sizeof(prefix));
    put32(data + 8, record.revision);
    put32(data + 12, checksum(data, 12));
    return true;
}
inline bool decode(const uint8_t *data, size_t size, Record &out) {
    if (!data || size != kBytes || memcmp(data, "BOOT", 4) ||
        data[4] != 1 || data[5] > 1 || data[6] || data[7] ||
        !get32(data + 8) || get32(data + 12) != checksum(data, 12)) return false;
    out = Record{get32(data + 8), data[5] != 0};
    return true;
}
enum class ReadResult { Ok, Missing, Invalid, Failed };
enum class Result {
    NotLoaded, Ok, Missing, Invalid, ReadFailed, ReloadRequired, Conflict,
    RevisionExhausted, WriteUncertain, ReadbackUncertain
};
class Backend {
public:
    virtual ~Backend() = default;
    // Never write past capacity. False from write does not prove unchanged bytes.
    virtual ReadResult read(uint8_t *data, size_t capacity, size_t &size) = 0;
    virtual bool write(const uint8_t *data, size_t size) = 0;
};
// One serialized owner of the backend, not a cross-task lock or atomic CAS.
// No constructor IO, erase, framework initialization or application callbacks.
class Store {
    Backend &backend_;
    bool initialized_ = false, usable_ = false, hasRecord_ = false;
    Record record_ = {0, false};
    Result last_ = Result::NotLoaded;
    Result readRecord(Record &out) {
        uint8_t data[kBytes] = {};
        size_t size = 0;
        const ReadResult read = backend_.read(data, sizeof(data), size);
        if (read == ReadResult::Missing) return Result::Missing;
        if (read == ReadResult::Invalid) return Result::Invalid;
        if (read != ReadResult::Ok) return Result::ReadFailed;
        return decode(data, size, out) ? Result::Ok : Result::Invalid;
    }
    Result accept(Result result, const Record &record) {
        initialized_ = true;
        usable_ = result == Result::Ok || result == Result::Missing;
        if (result == Result::Ok) { record_ = record; hasRecord_ = true; }
        if (result == Result::Missing) { record_ = Record{0, false}; hasRecord_ = false; }
        last_ = result;
        return result;
    }
    Result uncertain(Result result) { usable_ = false; last_ = result; return result; }
public:
    explicit Store(Backend &backend) : backend_(backend) {}
    Store(const Store &) = delete;
    Store &operator=(const Store &) = delete;
    bool initialized() const { return initialized_; }
    bool usable() const { return usable_; }
    bool hasRecord() const { return hasRecord_; }
    bool enabled() const { return usable_ && hasRecord_ && record_.enabled; }
    // Last accepted record is diagnostic only while unusable.
    uint32_t revision() const { return record_.revision; }
    Result lastStorageResult() const { return last_; }
    Result load() {
        Record current = {};
        return accept(readRecord(current), current);
    }
    Result save(uint32_t expectedRevision, bool enabled) {
        if (!usable_) return Result::ReloadRequired;
        Record current = {};
        const Result loaded = readRecord(current);
        accept(loaded, current);
        if (!usable_) return loaded;
        if (expectedRevision != record_.revision) return Result::Conflict;
        if (hasRecord_ && record_.enabled == enabled) return Result::Ok;
        if (record_.revision == UINT32_MAX) return Result::RevisionExhausted;
        const Record candidate = {record_.revision + 1, enabled};
        uint8_t expected[kBytes] = {};
        if (!encode(candidate, expected, sizeof(expected))) return uncertain(Result::WriteUncertain);
        if (!backend_.write(expected, sizeof(expected))) return uncertain(Result::WriteUncertain);
        Record verified = {};
        if (readRecord(verified) != Result::Ok) return uncertain(Result::ReadbackUncertain);
        uint8_t actual[kBytes] = {};
        if (!encode(verified, actual, sizeof(actual)) || memcmp(actual, expected, kBytes))
            return uncertain(Result::ReadbackUncertain);
        return accept(Result::Ok, verified);
    }
};
} // namespace bootButtonShortcut
