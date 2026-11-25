#include "BootButtonShortcutNvsBackend.h"
#include <cassert>
#include <cstring>
#include <vector>
namespace b = bootButtonShortcut;
#if defined(ESP32)
namespace fake {
std::vector<uint8_t> data, pending;
bool space = false, key = false, persistOnError = false;
esp_err_t openError = ESP_OK, probeError = ESP_OK, fetchError = ESP_OK;
esp_err_t setError = ESP_OK, commitError = ESP_OK;
int fetchedSize = -1;
unsigned handles = 0, opens = 0, readOpens = 0, writeOpens = 0;
unsigned probes = 0, fetches = 0, sets = 0, commits = 0, closes = 0;
nvs_open_mode_t currentMode = NVS_READONLY;
void reset() {
    data.clear(); pending.clear(); space = key = persistOnError = false;
    openError = probeError = fetchError = setError = commitError = ESP_OK;
    fetchedSize = -1;
    handles = opens = readOpens = writeOpens = probes = fetches = sets = commits = closes = 0;
}
void install(uint32_t revision = 1, bool enabled = true) {
    data.resize(b::kBytes);
    assert(b::encode(b::Record{revision, enabled}, data.data(), data.size()));
    space = key = true;
}
void balanced() { assert(handles == 0 && closes <= opens); }
}
esp_err_t nvs_open(const char *name, nvs_open_mode_t mode, nvs_handle_t *handle) {
    assert(!std::strcmp(name, "wc-boot")); ++fake::opens;
    if (mode == NVS_READONLY) ++fake::readOpens;
    else { assert(mode == NVS_READWRITE); ++fake::writeOpens; }
    if (fake::openError != ESP_OK) return fake::openError;
    if (mode == NVS_READONLY && !fake::space) return ESP_ERR_NVS_NOT_FOUND;
    if (mode == NVS_READWRITE) fake::space = true;
    assert(fake::handles == 0); ++fake::handles;
    fake::currentMode = mode; *handle = 1; return ESP_OK;
}
esp_err_t nvs_get_blob(nvs_handle_t handle, const char *name, void *out, size_t *length) {
    assert(handle == 1 && fake::handles == 1 && !std::strcmp(name, "shortcut"));
    assert(fake::currentMode == NVS_READONLY);
    if (out) ++fake::fetches; else ++fake::probes;
    const esp_err_t error = out ? fake::fetchError : fake::probeError;
    if (error != ESP_OK) return error;
    if (!fake::key) return ESP_ERR_NVS_NOT_FOUND;
    if (!out) { *length = fake::data.size(); return ESP_OK; }
    if (*length < fake::data.size()) {
        *length = fake::data.size(); return ESP_ERR_NVS_INVALID_LENGTH;
    }
    if (!fake::data.empty()) std::memcpy(out, fake::data.data(), fake::data.size());
    *length = fake::fetchedSize < 0 ? fake::data.size() : size_t(fake::fetchedSize);
    return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t handle, const char *name, const void *data, size_t size) {
    assert(handle == 1 && fake::handles == 1 && !std::strcmp(name, "shortcut"));
    assert(fake::currentMode == NVS_READWRITE && size == b::kBytes); ++fake::sets;
    if (fake::setError != ESP_OK) return fake::setError;
    const uint8_t *bytes = static_cast<const uint8_t *>(data);
    fake::pending.assign(bytes, bytes + size); return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t handle) {
    assert(handle == 1 && fake::handles == 1 && fake::currentMode == NVS_READWRITE);
    ++fake::commits;
    if (fake::commitError == ESP_OK || fake::persistOnError) {
        fake::data = fake::pending; fake::key = true;
    }
    return fake::commitError;
}
void nvs_close(nvs_handle_t handle) {
    assert(handle == 1 && fake::handles == 1); --fake::handles; ++fake::closes;
}
#endif
int main() {
    static_assert(b::kBytes == 16, "shortcut record size");
    uint8_t portable[b::kBytes] = {}; b::Record decoded = {};
    assert(b::encode(b::Record{1, false}, portable, sizeof(portable)));
    assert(b::decode(portable, sizeof(portable), decoded) && !decoded.enabled);
#if defined(ESP32)
    uint8_t data[b::kBytes + 1] = {}; data[b::kBytes] = 0xa5;
    size_t size = 99;
    fake::reset(); b::NvsBackend backend; b::Store missing(backend);
    assert(!fake::opens && !missing.enabled());
    assert(missing.load() == b::Result::Missing);
    assert(!fake::space && fake::readOpens == 1 && !fake::writeOpens && !fake::sets && !fake::commits);
    for (unsigned i = 0; i < 10000; ++i) assert(!missing.enabled());
    assert(fake::opens == 1); fake::balanced();
    fake::space = true; size = 99;
    assert(backend.read(data, b::kBytes, size) == b::ReadResult::Missing && size == 0);
    fake::balanced();
    fake::reset(); fake::install();
    assert(backend.read(nullptr, b::kBytes, size) == b::ReadResult::Failed && size == 0);
    assert(backend.read(data, b::kBytes - 1, size) == b::ReadResult::Invalid && size == 0);
    assert(!fake::opens);
    assert(backend.read(data, b::kBytes, size) == b::ReadResult::Ok && size == b::kBytes);
    assert(data[b::kBytes] == 0xa5); fake::balanced();
    for (size_t length : {size_t(0), size_t(15), size_t(17), size_t(4096)}) {
        fake::reset(); fake::install(); fake::data.resize(length); size = 99;
        assert(backend.read(data, b::kBytes, size) == b::ReadResult::Invalid && size == 0);
        assert(!fake::fetches && !fake::writeOpens && data[b::kBytes] == 0xa5); fake::balanced();
    }
    for (esp_err_t error : {ESP_FAIL, ESP_ERR_NVS_NOT_INITIALIZED}) {
        fake::reset(); fake::openError = error; size = 99;
        assert(backend.read(data, b::kBytes, size) == b::ReadResult::Failed && size == 0);
        assert(!fake::closes); fake::balanced();
    }
    for (esp_err_t error : {ESP_FAIL, ESP_ERR_NVS_TYPE_MISMATCH, ESP_ERR_NVS_NOT_FOUND}) {
        fake::reset(); fake::install(); fake::probeError = error; size = 99;
        const b::ReadResult expected = error == ESP_ERR_NVS_NOT_FOUND ? b::ReadResult::Missing :
            error == ESP_ERR_NVS_TYPE_MISMATCH ? b::ReadResult::Invalid : b::ReadResult::Failed;
        assert(backend.read(data, b::kBytes, size) == expected && size == 0 && !fake::fetches);
        fake::balanced();
    }
    for (esp_err_t error : {ESP_FAIL, ESP_ERR_NVS_TYPE_MISMATCH, ESP_ERR_NVS_NOT_FOUND, ESP_ERR_NVS_INVALID_LENGTH}) {
        fake::reset(); fake::install(); fake::fetchError = error; size = 99;
        assert(backend.read(data, b::kBytes, size) == b::ReadResult::Failed && size == 0);
        assert(data[b::kBytes] == 0xa5); fake::balanced();
    }
    for (int length : {0, 15, 17}) {
        fake::reset(); fake::install(); fake::fetchedSize = length; size = 99;
        assert(backend.read(data, b::kBytes, size) == b::ReadResult::Failed && size == 0);
        assert(data[b::kBytes] == 0xa5); fake::balanced();
    }
    fake::reset(); fake::install();
    const auto good = fake::data; auto bad = good; bad[12] ^= 1;
    assert(!backend.write(nullptr, b::kBytes) && !backend.write(good.data(), 15));
    assert(!backend.write(good.data(), 17) && !backend.write(bad.data(), bad.size()));
    assert(!fake::opens && !fake::sets && !fake::commits);
    fake::openError = ESP_FAIL;
    assert(!backend.write(good.data(), good.size()) && !fake::sets && !fake::commits);
    fake::balanced();
    for (esp_err_t error : {ESP_FAIL, ESP_ERR_NVS_TYPE_MISMATCH}) {
        fake::reset(); fake::install(); fake::setError = error;
        assert(!backend.write(good.data(), good.size()));
        assert(fake::sets == 1 && !fake::commits && fake::data == good); fake::balanced();
    }
    fake::reset(); fake::install(); b::Store live(backend);
    assert(live.load() == b::Result::Ok && live.enabled());
    assert(live.save(1, false) == b::Result::Ok && !live.enabled() && live.revision() == 2);
    assert(fake::sets == 1 && fake::commits == 1);
    assert(live.save(2, false) == b::Result::Ok && fake::sets == 1);
    assert(live.save(1, true) == b::Result::Conflict && fake::sets == 1); fake::balanced();
    for (bool persisted : {false, true}) {
        fake::reset(); fake::install(); b::Store faulted(backend);
        assert(faulted.load() == b::Result::Ok && faulted.enabled());
        fake::commitError = ESP_FAIL; fake::persistOnError = persisted;
        assert(faulted.save(1, false) == b::Result::WriteUncertain);
        assert(!faulted.enabled() && !faulted.usable() && fake::sets == 1);
        const unsigned opens = fake::opens;
        assert(faulted.save(1, false) == b::Result::ReloadRequired && fake::opens == opens);
        fake::commitError = ESP_OK;
        assert(faulted.load() == b::Result::Ok && faulted.enabled() == !persisted);
        assert(faulted.revision() == (persisted ? 2U : 1U) && fake::sets == 1); fake::balanced();
    }
    fake::reset(); fake::install(); fake::data[5] ^= 1; b::Store corrupt(backend);
    assert(corrupt.load() == b::Result::Invalid && !corrupt.enabled());
    assert(corrupt.save(1, true) == b::Result::ReloadRequired && !fake::writeOpens); fake::balanced();
    fake::reset(); fake::openError = ESP_ERR_NVS_NOT_INITIALIZED; b::Store unavailable(backend);
    assert(unavailable.load() == b::Result::ReadFailed && !unavailable.enabled());
    assert(unavailable.save(0, true) == b::Result::ReloadRequired && !fake::writeOpens);
    fake::balanced();
#endif
}
