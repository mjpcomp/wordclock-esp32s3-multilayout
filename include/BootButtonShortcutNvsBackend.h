#pragma once
#include "BootButtonShortcutSettings.h"
#if defined(ESP32)
#include <nvs.h>

namespace bootButtonShortcut {
// Dormant adapter. NVS initialization belongs to the framework/application.
// Only wc-boot/shortcut is addressed; no erase, repair or constructor IO.
class NvsBackend : public Backend {
public:
    ReadResult read(uint8_t *data, size_t capacity, size_t &size) override {
        size = 0;
        if (!data) return ReadResult::Failed;
        if (capacity < kBytes) return ReadResult::Invalid;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-boot", NVS_READONLY, &handle);
        if (error == ESP_ERR_NVS_NOT_FOUND) return ReadResult::Missing;
        if (error != ESP_OK) return ReadResult::Failed;
        size_t needed = 0;
        error = nvs_get_blob(handle, "shortcut", nullptr, &needed);
        if (error == ESP_ERR_NVS_NOT_FOUND) { nvs_close(handle); return ReadResult::Missing; }
        if (error == ESP_ERR_NVS_TYPE_MISMATCH) { nvs_close(handle); return ReadResult::Invalid; }
        if (error != ESP_OK) { nvs_close(handle); return ReadResult::Failed; }
        if (needed != kBytes || needed > capacity) {
            nvs_close(handle); return ReadResult::Invalid;
        }
        size_t actual = needed;
        error = nvs_get_blob(handle, "shortcut", data, &actual);
        nvs_close(handle);
        // Disappearance/type/size changes after probing are uncertain reads.
        if (error != ESP_OK || actual != needed) return ReadResult::Failed;
        size = actual;
        return ReadResult::Ok;
    }
    bool write(const uint8_t *data, size_t size) override {
        Record candidate = {};
        if (!decode(data, size, candidate)) return false;
        nvs_handle_t handle;
        esp_err_t error = nvs_open("wc-boot", NVS_READWRITE, &handle);
        if (error != ESP_OK) return false;
        error = nvs_set_blob(handle, "shortcut", data, size);
        if (error == ESP_OK) error = nvs_commit(handle);
        nvs_close(handle);
        // Store independently verifies readback; false is an uncertain outcome.
        return error == ESP_OK;
    }
};
} // namespace bootButtonShortcut
#endif
