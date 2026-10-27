// Real ArduinoJson serialization of the additive capability object only.
// The protocol hook is a separate change; this is not an end-to-end device test.
#include "BrightnessScheduleCapabilities.h"
#include "BrightnessScheduleProtocol.h"
#include <assert.h>
#include <string>

namespace caps = brightnessScheduleCapabilities;
static_assert(caps::SCHEMA == 1, "capability schema");
static_assert(caps::RENDERER_CACHE_COMPILED == EXPECT_CACHE, "cache flag");
static_assert(caps::SCHEDULE_OUTPUT_COMPILED == EXPECT_OUTPUT, "output flag");
#ifdef MAX_INPUT
static_assert(MAX_INPUT == 255, "Do not alter SDK macro");
#endif
static_assert(brightnessScheduleProtocol::kMaxInput == 2048, "Preserve wire input limit");

static void verify(JsonDocument &reply) {
  caps::appendTo(reply);
  JsonObjectConst facts = reply["capabilities"].as<JsonObjectConst>();
  assert(!facts.isNull() && facts.size() == 4);
  assert(facts["schema"] == 1);
  assert(facts["configurationProtocol"].is<bool>() && facts["configurationProtocol"].as<bool>());
  assert(facts["rendererCacheCompiled"].is<bool>());
  assert(facts["scheduleOutputCompiled"].is<bool>());
  assert(facts["rendererCacheCompiled"].as<bool>() == caps::RENDERER_CACHE_COMPILED);
  assert(facts["scheduleOutputCompiled"].as<bool>() == caps::SCHEDULE_OUTPUT_COMPILED);
  assert(!reply.overflowed());
  char output[brightnessScheduleProtocol::MIN_OUTPUT];
  const size_t expected = measureJson(reply);
  assert(expected < sizeof(output));
  const size_t written = serializeJson(reply, output, sizeof(output));
  assert(written == expected && output[written] == 0);
}

int main() {
  constexpr size_t budget = JSON_OBJECT_SIZE(10) + JSON_OBJECT_SIZE(4) +
      JSON_ARRAY_SIZE(16) + 16 * JSON_OBJECT_SIZE(3) + 512;
  DynamicJsonDocument reply(budget);
  reply["command"] = "brightness-schedule";
  reply["schema"] = 1;
  reply["requestId"] = std::string(32, 'r');
  reply["action"] = "get";
  reply["status"] = "loaded";
  reply["revision"] = 0xffffffffUL;
  reply["defaultTenths"] = 1000;
  JsonArray events = reply.createNestedArray("events");
  for (unsigned index = 0; index < 16; ++index) {
    JsonObject event = events.createNestedObject();
    event["minute"] = index * 90;
    event["targetTenths"] = 1000;
    event["fadeMinutes"] = 90;
  }
  verify(reply);
  assert(reply["events"].size() == 16);
  reply.clear();
  reply["command"] = "brightness-schedule";
  reply["schema"] = 1;
  reply["requestId"] = "missing";
  reply["action"] = "get";
  reply["status"] = "missing";
  reply["revision"] = 0;
  reply["defaultTenths"] = 1000;
  reply.createNestedArray("events");
  reply["draft"] = true;
  verify(reply);
  assert(reply["draft"].as<bool>());
  reply.clear();
  reply["command"] = "brightness-schedule";
  reply["schema"] = 1;
  reply["requestId"] = nullptr;
  reply["status"] = "invalid-request";
  verify(reply);
  return 0;
}
