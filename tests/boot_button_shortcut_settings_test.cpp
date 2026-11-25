#include "BootButtonShortcutSettings.h"
#include "BootButtonGestureModel.h"
#include <cassert>
#include <cstring>
#include <vector>
namespace b = bootButtonShortcut;

struct Fake : b::Backend {
    enum WriteMode { Normal, FalseUnchanged, FalseApplied, NoChange, Corrupt,
                     WrongValid, FailRead, InvalidRead, MissingRead, OversizeRead };
    std::vector<uint8_t> bytes;
    bool missing = true, failed = false, invalid = false, oversized = false;
    unsigned reads = 0, writes = 0;
    WriteMode mode = Normal;
    b::ReadResult read(uint8_t *data, size_t capacity, size_t &size) override {
        ++reads; size = 0;
        if (failed) return b::ReadResult::Failed;
        if (invalid) return b::ReadResult::Invalid;
        if (missing) return b::ReadResult::Missing;
        if (oversized) { size = capacity + 1; return b::ReadResult::Ok; }
        assert(bytes.size() <= capacity);
        std::memcpy(data, bytes.data(), bytes.size()); size = bytes.size();
        return b::ReadResult::Ok;
    }
    bool write(const uint8_t *data, size_t size) override {
        ++writes;
        if (mode == FalseUnchanged) return false;
        if (mode == NoChange) return true;
        bytes.assign(data, data + size); missing = false;
        if (mode == Corrupt) bytes[5] ^= 1;
        if (mode == WrongValid) {
            b::Record record = {}; assert(b::decode(bytes.data(), bytes.size(), record));
            record.enabled = !record.enabled;
            assert(b::encode(record, bytes.data(), bytes.size()));
        }
        if (mode == FailRead) failed = true;
        if (mode == InvalidRead) invalid = true;
        if (mode == MissingRead) missing = true;
        if (mode == OversizeRead) oversized = true;
        return mode != FalseApplied;
    }
    void seed(uint32_t revision, bool enabled) {
        bytes.resize(b::kBytes);
        assert(b::encode(b::Record{revision, enabled}, bytes.data(), bytes.size()));
        missing = failed = invalid = oversized = false;
    }
};

int main() {
    {
        uint8_t data[b::kBytes + 1] = {}; data[b::kBytes] = 0xa5;
        for (uint32_t revision : {1U, 2U, UINT32_MAX}) {
            for (bool enabled : {false, true}) {
                assert(b::encode(b::Record{revision, enabled}, data, b::kBytes));
                assert(data[b::kBytes] == 0xa5);
                b::Record decoded = {};
                assert(b::decode(data, b::kBytes, decoded));
                assert(decoded.revision == revision && decoded.enabled == enabled);
                for (size_t bit = 0; bit < b::kBytes * 8; ++bit) {
                    uint8_t corrupt[b::kBytes]; std::memcpy(corrupt, data, b::kBytes);
                    corrupt[bit / 8] ^= uint8_t(1U << (bit % 8));
                    b::Record unchanged = {99, true};
                    assert(!b::decode(corrupt, sizeof(corrupt), unchanged));
                    assert(unchanged.revision == 99 && unchanged.enabled);
                }
            }
        }
        b::Record record = {99, true};
        assert(!b::decode(nullptr, b::kBytes, record));
        for (size_t size = 0; size <= b::kBytes + 1; ++size)
            if (size != b::kBytes) assert(!b::decode(data, size, record));
        assert(!b::encode(b::Record{0, true}, data, sizeof(data)));
        assert(!b::encode(record, nullptr, b::kBytes));
        assert(!b::encode(record, data, b::kBytes - 1));
        for (unsigned field : {0U, 4U, 5U, 6U, 7U, 8U}) {
            assert(b::encode(b::Record{1, false}, data, b::kBytes));
            if (field == 8) b::put32(data + 8, 0);
            else data[field] = field == 5 ? 2 : 0xff;
            b::put32(data + 12, b::checksum(data, 12));
            assert(!b::decode(data, b::kBytes, record));
        }
    }
    {
        Fake backend; b::Store store(backend);
        assert(!store.initialized() && !store.usable() && !store.enabled());
        assert(store.lastStorageResult() == b::Result::NotLoaded);
        assert(store.save(0, true) == b::Result::ReloadRequired);
        assert(backend.reads == 0 && backend.writes == 0);
        assert(store.load() == b::Result::Missing);
        assert(store.usable() && !store.hasRecord() && !store.enabled());
        assert(backend.writes == 0);
        assert(store.save(1, true) == b::Result::Conflict && backend.writes == 0);
        assert(store.save(0, true) == b::Result::Ok);
        assert(store.enabled() && store.revision() == 1 && backend.writes == 1);
        assert(store.save(1, true) == b::Result::Ok && backend.writes == 1);
        assert(store.save(0, false) == b::Result::Conflict && backend.writes == 1);
        assert(store.save(1, false) == b::Result::Ok);
        assert(!store.enabled() && store.revision() == 2 && backend.writes == 2);
        b::Store reboot(backend);
        assert(!reboot.enabled() && reboot.load() == b::Result::Ok);
        assert(!reboot.enabled() && reboot.revision() == 2);
        backend.seed(3, true);
        assert(reboot.save(2, false) == b::Result::Conflict);
        assert(reboot.revision() == 3 && reboot.enabled() && backend.writes == 2);
    }
    {
        Fake backend; b::Store store(backend);
        assert(store.load() == b::Result::Missing);
        assert(store.save(0, false) == b::Result::Ok);
        assert(store.hasRecord() && !store.enabled() && store.revision() == 1);
        assert(backend.writes == 1);
    }
    for (unsigned kind = 0; kind < 5; ++kind) {
        Fake backend; backend.seed(1, true); b::Store store(backend);
        assert(store.load() == b::Result::Ok && store.enabled());
        if (kind == 0) backend.failed = true;
        if (kind == 1) backend.invalid = true;
        if (kind == 2) backend.bytes[0] ^= 1;
        if (kind == 3) backend.bytes.resize(3);
        if (kind == 4) backend.oversized = true;
        const b::Result expected = kind == 0 ? b::Result::ReadFailed : b::Result::Invalid;
        assert(store.load() == expected);
        assert(!store.enabled() && !store.usable());
        const unsigned reads = backend.reads;
        assert(store.save(1, true) == b::Result::ReloadRequired);
        assert(backend.reads == reads && backend.writes == 0);
        backend.seed(1, true);
        assert(store.load() == b::Result::Ok && store.enabled());
    }
    {
        Fake backend; backend.seed(1, true); b::Store store(backend);
        assert(store.load() == b::Result::Ok);
        backend.failed = true;
        assert(store.save(1, false) == b::Result::ReadFailed);
        assert(!store.enabled() && backend.writes == 0);
    }
    for (Fake::WriteMode mode : {Fake::FalseUnchanged, Fake::FalseApplied, Fake::NoChange,
         Fake::Corrupt, Fake::WrongValid, Fake::FailRead, Fake::InvalidRead,
         Fake::MissingRead, Fake::OversizeRead}) {
        Fake backend; backend.seed(1, true); b::Store store(backend);
        assert(store.load() == b::Result::Ok);
        backend.mode = mode;
        const b::Result expected = mode == Fake::FalseUnchanged || mode == Fake::FalseApplied
            ? b::Result::WriteUncertain : b::Result::ReadbackUncertain;
        assert(store.save(1, false) == expected);
        assert(store.lastStorageResult() == expected && !store.enabled() && !store.usable());
        const unsigned reads = backend.reads;
        assert(store.save(1, false) == b::Result::ReloadRequired);
        assert(backend.writes == 1 && backend.reads == reads);
        if (mode == Fake::FalseApplied) {
            assert(store.load() == b::Result::Ok);
            assert(store.revision() == 2 && !store.enabled());
        }
    }
    {
        Fake backend; backend.seed(UINT32_MAX, true); b::Store store(backend);
        assert(store.load() == b::Result::Ok);
        assert(store.save(UINT32_MAX, true) == b::Result::Ok);
        assert(store.save(UINT32_MAX, false) == b::Result::RevisionExhausted);
        assert(store.enabled() && backend.writes == 0);
    }
    {
        Fake backend; backend.failed = true; b::Store store(backend);
        assert(store.load() == b::Result::ReadFailed);
        bootButtonGesture::Model gesture;
        using bootButtonGesture::Action;
        assert(gesture.sample(0, false, store.enabled()) == Action::None);
        assert(gesture.sample(100, true, store.enabled()) == Action::None);
        assert(gesture.sample(140, true, store.enabled()) == Action::None);
        assert(gesture.sample(8140, true, store.enabled()) == Action::None);
        assert(gesture.sample(9000, false, store.enabled()) == Action::None);
        assert(gesture.sample(9040, false, store.enabled()) == Action::WiFiSetup);
    }
}
