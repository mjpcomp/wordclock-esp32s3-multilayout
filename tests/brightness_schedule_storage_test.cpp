#include "BrightnessScheduleStorage.h"
#include <assert.h>
#include <string.h>
#include <vector>
using namespace brightnessScheduleStorage;
static std::vector<uint8_t> bytes(const Record &r) {
    uint8_t buffer[MAX_BYTES] = {};
    size_t size = 0;
    assert(encode(r, buffer, sizeof(buffer), size));
    return std::vector<uint8_t>(buffer, buffer + size);
}
class Fake : public Backend {
public:
    std::vector<uint8_t> data;
    bool missing = true, failRead = false, failWrite = false;
    bool changedDespiteFailure = false, failReadback = false, corruptReadback = false, differentReadback = false;
    unsigned reads = 0, writes = 0;
    ReadResult read(uint8_t *dest, size_t capacity, size_t &size) override {
        ++reads;
        if (failRead || (failReadback && writes)) return ReadResult::Failed;
        if (missing) return ReadResult::Missing;
        if (data.size() > capacity) return ReadResult::Invalid;
        size = data.size();
        if (size) memcpy(dest, data.data(), size);
        if (corruptReadback && writes && size) dest[size - 1] ^= 1;
        if (differentReadback && writes && size >= MIN_BYTES) {
            dest[6] ^= 1; put32(dest + size - 4, crc32(dest, size - 4));
        }
        return ReadResult::Ok;
    }
    bool write(const uint8_t *src, size_t size) override {
        ++writes;
        if (!failWrite || changedDespiteFailure) { data.assign(src, src + size); missing = false; }
        return !failWrite;
    }
};
#if defined(ESP32)
namespace native {
std::vector<uint8_t> data, pending;
bool exists = false, openError = false, getError = false, setError = false;
bool commitError = false, persistOnError = false, wrongType = false;
unsigned handles = 0, readOpens = 0, writeOpens = 0, commits = 0, sets = 0;
void reset() {
    data.clear(); pending.clear(); exists = openError = getError = setError = false;
    commitError = persistOnError = wrongType = false;
    handles = readOpens = writeOpens = commits = sets = 0;
}
}
esp_err_t nvs_open(const char *name, nvs_open_mode_t mode, nvs_handle_t *handle) {
    assert(strcmp(name, "wc-bright") == 0);
    if (mode == NVS_READONLY) ++native::readOpens; else ++native::writeOpens;
    if (native::openError) return ESP_FAIL;
    if (!native::exists && mode == NVS_READONLY) return ESP_ERR_NVS_NOT_FOUND;
    if (mode == NVS_READWRITE) native::exists = true;
    ++native::handles; *handle = 1; return ESP_OK;
}
esp_err_t nvs_get_blob(nvs_handle_t handle, const char *key, void *out, size_t *size) {
    assert(handle == 1 && strcmp(key, "schedule") == 0);
    if (native::getError) return ESP_FAIL;
    if (native::wrongType) return ESP_ERR_NVS_TYPE_MISMATCH;
    if (native::data.empty()) return ESP_ERR_NVS_NOT_FOUND;
    if (!out) { *size = native::data.size(); return ESP_OK; }
    if (*size < native::data.size()) return ESP_FAIL;
    memcpy(out, native::data.data(), native::data.size()); *size = native::data.size();
    return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t handle, const char *key, const void *data, size_t size) {
    assert(handle == 1 && strcmp(key, "schedule") == 0); ++native::sets;
    if (native::setError) return ESP_FAIL;
    const uint8_t *p = static_cast<const uint8_t *>(data);
    native::pending.assign(p, p + size); return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t handle) {
    assert(handle == 1); ++native::commits;
    if (!native::commitError || native::persistOnError) native::data = native::pending;
    return native::commitError ? ESP_FAIL : ESP_OK;
}
void nvs_close(nvs_handle_t handle) { assert(handle == 1 && native::handles); --native::handles; }
#endif
int main() {
    assert(MAX_BYTES == 112);
    assert(crc32(reinterpret_cast<const uint8_t *>("123456789"), 9) == 0xcbf43926UL);
    Record r = {}; r.revision = 1; r.schedule.defaultTenths = 1000;
    const uint8_t golden[] = {0x57,0x43,0x42,0x53,1,0,0xe8,3,1,0,0,0,0xe8,0x24,0xad,0x64};
    std::vector<uint8_t> b = bytes(r);
    assert(b.size() == sizeof(golden) && !memcmp(b.data(), golden, sizeof(golden)));
    Record out = {}; out.revision = 999;
    size_t unchangedSize = 77;
    uint8_t shortBuffer[8] = {};
    assert(!encode(r, shortBuffer, sizeof(shortBuffer), unchangedSize) && unchangedSize == 77);
    std::vector<uint8_t> zeroRevision = b; put32(zeroRevision.data() + 8, 0);
    put32(zeroRevision.data() + zeroRevision.size() - 4, crc32(zeroRevision.data(), zeroRevision.size() - 4));
    assert(decode(zeroRevision.data(), zeroRevision.size(), out) == Result::ResetRequired);
    assert(decode(b.data(), b.size(), out) == Result::Ok && out.revision == 1);
    for (size_t bit = 0; bit < b.size() * 8; ++bit) {
        std::vector<uint8_t> bad = b; bad[bit / 8] ^= 1 << (bit % 8); out.revision = 999;
        assert(decode(bad.data(), bad.size(), out) == Result::ResetRequired && out.revision == 999);
    }
    std::vector<uint8_t> bad = b; put16(bad.data() + 6, 1001);
    put32(bad.data() + bad.size() - 4, crc32(bad.data(), bad.size() - 4));
    assert(decode(bad.data(), bad.size(), out) == Result::ResetRequired);
    assert(decode(b.data(), b.size() - 1, out) == Result::ResetRequired);
    bad = b; bad.push_back(0); assert(decode(bad.data(), bad.size(), out) == Result::ResetRequired);
    Record maximum = r; maximum.schedule.count = 16;
    for (uint8_t i = 0; i < 16; ++i) maximum.schedule.events[i] = {uint16_t(i * 90), uint16_t(i * 50), 90};
    b = bytes(maximum); assert(b.size() == 112);
    assert(decode(b.data(), b.size(), out) == Result::Ok && out.schedule.count == 16);
    Fake f; Store store(f); out.revision = 999;
    assert(store.load(out) == Result::Missing && out.revision == 999 && !f.writes);
    brightnessSchedule::Schedule s = {}; s.defaultTenths = 400;
    assert(store.save(0, s, out) == Result::Ok && out.revision == 1 && f.writes == 1);
    const unsigned savedWrites = f.writes;
    assert(store.load(out) == Result::Ok && f.writes == savedWrites);
    assert(store.save(0, s, out) == Result::Conflict && f.writes == savedWrites);
    brightnessSchedule::Schedule invalid = s; invalid.defaultTenths = 1001;
    assert(store.save(1, invalid, out) == Result::InvalidInput && f.writes == savedWrites);
    assert(store.reset(1, out) == Result::Ok && out.revision == 2 && out.schedule.count == 0 && out.schedule.defaultTenths == 1000);
    Fake corrupt; corrupt.missing = false; corrupt.data.assign(3, 1); Store broken(corrupt);
    out.revision = 999;
    assert(broken.load(out) == Result::ResetRequired && out.revision == 999 && !corrupt.writes);
    assert(broken.save(0, s, out) == Result::ResetRequired && !corrupt.writes);
    assert(broken.reset(0, out) == Result::Ok && out.revision == 1);
    Fake io; io.failRead = true; Store unavailable(io); out.revision = 999;
    assert(unavailable.reset(0, out) == Result::ReadFailed && !io.writes && out.revision == 999);
    Fake uncertain; uncertain.failWrite = uncertain.changedDespiteFailure = true;
    Store ambiguous(uncertain); out.revision = 999;
    assert(ambiguous.save(0, s, out) == Result::WriteUncertain && out.revision == 999);
    uncertain.failWrite = false;
    assert(ambiguous.save(0, s, out) == Result::Conflict);
    Fake readback; readback.failReadback = true; Store verify(readback); out.revision = 999;
    assert(verify.save(0, s, out) == Result::ReadbackUncertain && out.revision == 999);
    Fake mismatch; mismatch.corruptReadback = true; Store mismatchStore(mismatch);
    assert(mismatchStore.save(0, s, out) == Result::ReadbackUncertain);
    Fake different; different.differentReadback = true; Store differentStore(different);
    assert(differentStore.save(0, s, out) == Result::ReadbackUncertain);
    Fake exhausted; r.revision = 0xffffffffUL; exhausted.data = bytes(r); exhausted.missing = false;
    Store full(exhausted); assert(full.save(0xffffffffUL, s, out) == Result::RevisionExhausted && !exhausted.writes);
#if defined(ESP32)
    native::reset(); NvsBackend nvs; Store device(nvs); out.revision = 999;
    assert(!native::readOpens && !native::writeOpens && !native::commits);
    assert(device.load(out) == Result::Missing && !native::exists && !native::writeOpens);
    native::exists = true;
    assert(device.load(out) == Result::Missing && !native::handles && !native::writeOpens);
    assert(device.save(0, s, out) == Result::Ok && out.revision == 1 && !native::handles);
    const unsigned commits = native::commits;
    assert(device.load(out) == Result::Ok && native::commits == commits && !native::handles);
    native::wrongType = true;
    assert(device.load(out) == Result::ResetRequired && !native::handles);
    native::wrongType = false; native::getError = true;
    assert(device.load(out) == Result::ReadFailed && !native::handles);
    native::getError = false; native::setError = true; out.revision = 999;
    assert(device.save(1, s, out) == Result::WriteUncertain && out.revision == 999 && !native::handles);
    native::setError = false; native::commitError = native::persistOnError = true;
    assert(device.save(1, s, out) == Result::WriteUncertain && !native::handles);
    native::commitError = false;
    assert(device.load(out) == Result::Ok && out.revision == 2);
    native::data.assign(113, 0);
    assert(device.load(out) == Result::ResetRequired && !native::handles);
    native::openError = true;
    assert(device.reset(0, out) == Result::ReadFailed && !native::handles);
#endif
    return 0;
}
