#pragma once
#include "OnboardIndicatorStorage.h"
#if defined(ESP32)
#include <nvs.h>

namespace onboardIndicatorStorage {
// Dormant adapter: no instance, initialization, erase or constructor IO here.
// NVS must already be initialized by the application/framework.
class NvsBackend : public Backend {
public:
    ReadResult read(uint8_t *data, size_t capacity, size_t &size) override {
        size = 0;
        if (!data) return ReadResult::Failed;
        if (capacity < onboardIndicatorRecord::kBytes) return ReadResult::Invalid;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-onboard", NVS_READONLY, &handle);
        if (error == ESP_ERR_NVS_NOT_FOUND) return ReadResult::Missing;
        if (error != ESP_OK) return ReadResult::Failed;
        size_t needed = 0;
        error = nvs_get_blob(handle, "policy", nullptr, &needed);
        if (error == ESP_ERR_NVS_NOT_FOUND) { nvs_close(handle); return ReadResult::Missing; }
        if (error == ESP_ERR_NVS_TYPE_MISMATCH) { nvs_close(handle); return ReadResult::Invalid; }
        if (error != ESP_OK) { nvs_close(handle); return ReadResult::Failed; }
        if (needed != onboardIndicatorRecord::kBytes || needed > capacity) {
            nvs_close(handle); return ReadResult::Invalid;
        }
        size_t actual = needed;
        error = nvs_get_blob(handle, "policy", data, &actual);
        nvs_close(handle);
        // A key disappearing/changing during a read is not a fresh default.
        if (error != ESP_OK || actual != needed) return ReadResult::Failed;
        size = actual;
        return ReadResult::Ok;
    }
    bool write(const uint8_t *data, size_t size) override {
        onboardIndicatorRecord::Record candidate = {};
        if (!onboardIndicatorRecord::decode(data, size, candidate)) return false;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-onboard", NVS_READWRITE, &handle);
        if (error != ESP_OK) return false;
        error = nvs_set_blob(handle, "policy", data, size);
        if (error == ESP_OK) error = nvs_commit(handle);
        nvs_close(handle);
        // False is uncertain; Store still requires independent verified readback.
        return error == ESP_OK;
    }
};
} // namespace onboardIndicatorStorage
#endif
