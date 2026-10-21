#pragma once
#include "BrightnessScheduleStorage.h"
#include <ArduinoJson.h>
#include <stddef.h>
#include <string.h>

namespace brightnessScheduleProtocol {
namespace storage = brightnessScheduleStorage;
namespace schedule = brightnessSchedule;
constexpr size_t MAX_INPUT = 2048;
constexpr size_t MIN_OUTPUT = 2048;
constexpr size_t REQUEST_CAPACITY = JSON_OBJECT_SIZE(7) + JSON_ARRAY_SIZE(16) + 16 * JSON_OBJECT_SIZE(3) + MAX_INPUT + 128;
constexpr size_t RESPONSE_CAPACITY = JSON_OBJECT_SIZE(10) + JSON_ARRAY_SIZE(16) + 16 * JSON_OBJECT_SIZE(3) + 512;
static_assert(schedule::MAX_EVENTS == 16, "Review protocol budgets when capacity changes");
enum class Action { Get, Save, Reset };
struct Request {
  Action action;
  char id[33];
  uint32_t revision;
  schedule::Schedule schedule;
};
inline bool space(uint8_t c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }
inline bool completeObject(const uint8_t *data, size_t size, size_t &keys) {
  if (!data || !size || size > MAX_INPUT) return false;
  size_t first = 0;
  while (first < size && space(data[first])) ++first;
  if (first == size || data[first] != '{') return false;
  size_t depth = 0, count = 0;
  bool quoted = false, escaped = false, closedString = false;
  for (size_t i = first; i < size; ++i) {
    const uint8_t c = data[i];
    if (quoted) {
      if (c < 0x20) return false;
      if (escaped) escaped = false;
      else if (c == '\\') escaped = true;
      else if (c == '"') { quoted = false; closedString = true; }
      continue;
    }
    if (space(c)) continue;
    if (c == '"') { quoted = true; closedString = false; continue; }
    if (c == ':') {
      if (!closedString) return false;
      ++count; closedString = false; continue;
    }
    closedString = false;
    if (c >= '0' && c <= '9') {
      size_t last = i;
      while (last + 1 < size && data[last + 1] >= '0' && data[last + 1] <= '9') ++last;
      if (c == '0' && last != i) return false;
      i = last; continue;
    }
    if (c == 't' || c == 'f' || c == 'n') {
      const char *word = c == 't' ? "true" : c == 'f' ? "false" : "null";
      const size_t count = strlen(word);
      if (size - i < count || memcmp(data + i, word, count)) return false;
      i += count - 1; continue;
    }
    if (c != ',' && c != '{' && c != '}' && c != '[' && c != ']') return false;
    if (c == '{' || c == '[') { if (++depth > 4) return false; }
    else if (c == '}' || c == ']') {
      if (!depth) return false;
      --depth;
      if (!depth) {
        for (size_t j = i + 1; j < size; ++j) if (!space(data[j])) return false;
        keys = count;
        return c == '}';
      }
    }
  }
  return false;
}
inline bool equals(JsonString value, const char *literal) {
  return value.c_str() && value.size() == strlen(literal) && !memcmp(value.c_str(), literal, value.size());
}
inline bool stringIs(JsonVariantConst value, const char *literal) {
  return value.is<const char *>() && equals(value.as<JsonString>(), literal);
}
inline bool fields(JsonObjectConst obj, const char *const *names, size_t count) {
  if (obj.isNull() || obj.size() != count) return false;
  for (JsonPairConst pair : obj) {
    bool found = false;
    for (size_t i = 0; i < count; ++i) if (equals(pair.key(), names[i])) found = true;
    if (!found) return false;
  }
  return true;
}
inline bool number(JsonVariantConst value, uint32_t limit, uint32_t &out) {
  if (value.is<bool>() || !value.is<uint32_t>()) return false;
  const uint32_t n = value.as<uint32_t>();
  if (n > limit) return false;
  out = n;
  return true;
}
inline bool parse(const uint8_t *data, size_t size, Request &out, char (&correlation)[33]) {
  correlation[0] = 0;
  size_t keyCount = 0;
  if (!completeObject(data, size, keyCount)) return false;
  DynamicJsonDocument doc(REQUEST_CAPACITY);
  if (doc.capacity() < REQUEST_CAPACITY) return false;
  if (deserializeJson(doc, reinterpret_cast<const char *>(data), size, DeserializationOption::NestingLimit(4))) return false;
  JsonObjectConst obj = doc.as<JsonObjectConst>();
  if (obj.isNull() || !stringIs(obj["command"], "brightness-schedule")) return false;
  uint32_t n = 0;
  if (!obj["requestId"].is<const char *>()) return false;
  JsonString id = obj["requestId"].as<JsonString>();
  if (!id.size() || id.size() > 32) return false;
  for (size_t i = 0; i < id.size(); ++i) {
    const char c = id.c_str()[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
       (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
  }
  memcpy(correlation, id.c_str(), id.size()); correlation[id.size()] = 0;
  if (!number(obj["schema"], 1, n) || n != 1) return false;
  Request parsed = {};
  memcpy(parsed.id, id.c_str(), id.size());
  const char *const getKeys[] = {"command", "schema", "requestId", "action"};
  const char *const saveKeys[] = {"command", "schema", "requestId", "action", "expectedRevision", "defaultTenths", "events"};
  const char *const resetKeys[] = {"command", "schema", "requestId", "action", "expectedRevision", "confirmReset"};
  if (stringIs(obj["action"], "get")) {
    if (!fields(obj, getKeys, 4) || keyCount != 4) return false;
    parsed.action = Action::Get;
  } else {
    if (!number(obj["expectedRevision"], 0xffffffffUL, parsed.revision)) return false;
    if (stringIs(obj["action"], "reset")) {
      if (!fields(obj, resetKeys, 6) || keyCount != 6 ||
        !obj["confirmReset"].is<bool>() || !obj["confirmReset"].as<bool>()) return false;
      parsed.action = Action::Reset;
    } else if (stringIs(obj["action"], "save")) {
      if (!fields(obj, saveKeys, 7) || !number(obj["defaultTenths"], 1000, n)) return false;
      parsed.action = Action::Save;
      parsed.schedule.defaultTenths = static_cast<uint16_t>(n);
      JsonArrayConst events = obj["events"].as<JsonArrayConst>();
      if (events.isNull() || events.size() > 16 || keyCount != 7 + 3 * events.size()) return false;
      parsed.schedule.count = static_cast<uint8_t>(events.size());
      const char *const eventKeys[] = {"minute", "targetTenths", "fadeMinutes"};
      uint8_t i = 0;
      for (JsonVariantConst value : events) {
        JsonObjectConst event = value.as<JsonObjectConst>();
        if (!fields(event, eventKeys, 3) || !number(event["minute"], 1439, n)) return false;
        parsed.schedule.events[i].minute = static_cast<uint16_t>(n);
        if (!number(event["targetTenths"], 1000, n)) return false;
        parsed.schedule.events[i].targetTenths = static_cast<uint16_t>(n);
        if (!number(event["fadeMinutes"], 1439, n)) return false;
        parsed.schedule.events[i].fadeMinutes = static_cast<uint16_t>(n);
        ++i;
      }
      if (!schedule::valid(parsed.schedule)) return false;
    } else return false;
  }
  out = parsed;
  return true;
}
inline const char *actionName(Action action) {
  switch (action) { case Action::Get: return "get"; case Action::Save: return "save"; case Action::Reset: return "reset"; }
  return "unknown";
}
inline const char *statusName(storage::Result result, Action action) {
  using storage::Result;
  switch (result) {
  case Result::Ok: return action == Action::Get ? "loaded" : action == Action::Save ? "saved" : "reset";
  case Result::Missing: return "missing";
  case Result::ResetRequired: return "reset-required";
  case Result::ReadFailed: return "read-failed";
  case Result::InvalidInput: return "invalid-request";
  case Result::Conflict: return "conflict";
  case Result::RevisionExhausted: return "revision-exhausted";
  case Result::WriteUncertain: return "write-uncertain";
  case Result::ReadbackUncertain: return "readback-uncertain";
  }
  return "error";
}
inline void addRecord(JsonDocument &reply, const storage::Record &record) {
  reply["revision"] = record.revision;
  reply["defaultTenths"] = record.schedule.defaultTenths;
  JsonArray events = reply.createNestedArray("events");
  for (uint8_t i = 0; i < record.schedule.count; ++i) {
    const schedule::Event &e = record.schedule.events[i];
    JsonObject event = events.createNestedObject();
    event["minute"] = e.minute; event["targetTenths"] = e.targetTenths; event["fadeMinutes"] = e.fadeMinutes;
  }
}
inline bool handle(storage::Store &store, const uint8_t *input, size_t length,
         char *output, size_t capacity, size_t &used) {
  used = 0;
  if (!output || capacity < MIN_OUTPUT) return false;
  Request request = {};
  char correlation[33] = {};
  const bool valid = parse(input, length, request, correlation);
  DynamicJsonDocument reply(RESPONSE_CAPACITY);
  if (reply.capacity() < RESPONSE_CAPACITY) return false;
  reply["command"] = "brightness-schedule";
  reply["schema"] = 1;
  if (!valid) {
    if (correlation[0]) reply["requestId"] = correlation; else reply["requestId"] = nullptr;
    reply["status"] = "invalid-request";
  }
  else {
    reply["requestId"] = request.id;
    reply["action"] = actionName(request.action);
    storage::Record record = {};
    using storage::Result;
    Result result = Result::InvalidInput;
    if (request.action == Action::Get) result = store.load(record);
    else if (request.action == Action::Save) result = store.save(request.revision, request.schedule, record);
    else if (request.action == Action::Reset) result = store.reset(request.revision, record);
    reply["status"] = statusName(result, request.action);
    if (result == Result::Ok) addRecord(reply, record);
    else if (result == Result::Missing) {
      record.schedule.defaultTenths = 1000;
      addRecord(reply, record); reply["draft"] = true;
    } else if (result == Result::ResetRequired) reply["revision"] = 0;
    else reply["reloadRequired"] = true;
  }
  const size_t expected = measureJson(reply);
  if (reply.overflowed() || expected >= capacity) return false;
  const size_t written = serializeJson(reply, output, capacity);
  if (written != expected || written >= capacity) { output[0] = '\0'; return false; }
  output[written] = '\0'; used = written;
  return true;
}
} // namespace brightnessScheduleProtocol
