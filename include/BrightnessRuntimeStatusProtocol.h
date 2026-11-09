#pragma once
#include "BrightnessScheduleRuntimeOwner.h"
#include "BrightnessScheduleProtocol.h"
namespace brightnessRuntimeStatusProtocol {
namespace cfg = brightnessScheduleProtocol;
namespace owner = brightnessScheduleRuntimeOwner;
namespace storage = brightnessScheduleStorage;
enum class BackendKind { Unknown, None, Virtual, Physical };
enum class Result { NotRuntime, Handled, Unavailable };
struct State {
    owner::Observation observation;
    BackendKind backend;
    bool cacheCompiled, outputCompiled, rendererAttached;
};
using Provider = State (*)(void *);
constexpr size_t kMinOutput = cfg::MIN_OUTPUT;
constexpr size_t kResponseCapacity = JSON_OBJECT_SIZE(13) + JSON_OBJECT_SIZE(10) + JSON_OBJECT_SIZE(4) + 512;
inline const char *backendName(BackendKind kind) {
    switch (kind) {
    case BackendKind::None: return "none";
    case BackendKind::Virtual: return "virtual";
    case BackendKind::Physical: return "physical";
    case BackendKind::Unknown: return "unknown";
    }
    return "unknown";
}
inline const char *storageName(storage::Result result) {
    using storage::Result;
    switch (result) {
    case Result::Ok: return "ok";
    case Result::Missing: return "missing";
    case Result::ResetRequired: return "reset-required";
    case Result::ReadFailed: return "read-failed";
    case Result::InvalidInput: return "invalid-input";
    case Result::Conflict: return "conflict";
    case Result::RevisionExhausted: return "revision-exhausted";
    case Result::WriteUncertain: return "write-uncertain";
    case Result::ReadbackUncertain: return "readback-uncertain";
    }
    return "unknown";
}
inline bool copyId(JsonVariantConst value, char (&id)[33]) {
    id[0]=0;
    if (!value.is<const char *>()) return false;
    const JsonString text=value.as<JsonString>();
    if (!text.size() || text.size()>32) return false;
    for (size_t i=0;i<text.size();++i) {
        const char c=text.c_str()[i];
        if (!((c>='a' && c<='z') || (c>='A' && c<='Z') ||
              (c>='0' && c<='9') || c=='_' || c=='-')) return false;
    }
    memcpy(id,text.c_str(),text.size()); id[text.size()]=0;
    return true;
}
inline void append(JsonDocument &reply, const State &state) {
    const owner::Observation &value=state.observation;
    reply["initialized"]=value.initialized; reply["hasAccepted"]=value.hasAccepted;
    reply["acceptedRevision"]=value.acceptedRevision;
    reply["observedStorageFault"]=value.observedStorageFault;
    reply["pendingEvaluation"]=value.pendingEvaluation;
    reply["lastStorageResult"]=storageName(value.lastResult);
    if (!value.hasSample) reply["sample"]=nullptr;
    else {
        JsonObject sample=reply.createNestedObject("sample");
        sample["ageMs"]=value.sampleAgeMs; sample["gain"]=value.decision.gain;
        sample["revision"]=value.decision.revision; sample["scheduled"]=value.decision.scheduled;
        sample["pausedAutomatic"]=value.decision.pausedAutomatic;
        sample["waitingForTime"]=value.decision.waitingForTime;
        sample["storageFault"]=value.decision.storageFault;
        sample["automatic"]=value.automatic; sample["masterOn"]=value.masterOn;
        sample["timeValid"]=value.timeValid;
    }
    JsonObject backend=reply.createNestedObject("backend");
    backend["kind"]=backendName(state.backend); backend["cacheCompiled"]=state.cacheCompiled;
    backend["outputCompiled"]=state.outputCompiled; backend["rendererAttached"]=state.rendererAttached;
}
inline Result handle(const uint8_t *input, size_t length, char *output, size_t capacity,
                     size_t &used, Provider read, void *context) {
    used=0; size_t keys=0;
    if (!cfg::completeObject(input,length,keys)) return Result::NotRuntime;
    DynamicJsonDocument request(cfg::REQUEST_CAPACITY);
    if (request.capacity()<cfg::REQUEST_CAPACITY) return Result::Unavailable;
    if (deserializeJson(request,reinterpret_cast<const char *>(input),length,
                        DeserializationOption::NestingLimit(4))) return Result::NotRuntime;
    const JsonObjectConst obj=request.as<JsonObjectConst>();
    if (obj.isNull() || !cfg::stringIs(obj["command"],"brightness-runtime")) return Result::NotRuntime;
    if (!output || capacity<kMinOutput) return Result::Unavailable;
    char id[33]={}; const bool identified=copyId(obj["requestId"],id);
    uint32_t schema=0;
    const char *const names[]={"command","schema","requestId","action"};
    const bool valid=identified && keys==4 && cfg::fields(obj,names,4) &&
        cfg::number(obj["schema"],1,schema) && schema==1 && cfg::stringIs(obj["action"],"get");
    DynamicJsonDocument reply(kResponseCapacity);
    if (reply.capacity()<kResponseCapacity) return Result::Unavailable;
    reply["command"]="brightness-runtime"; reply["schema"]=1;
    if (identified) reply["requestId"]=id; else reply["requestId"]=nullptr;
    reply["action"]="get";
    reply["status"]=!valid ? "invalid-request" : !read ? "unavailable" : "snapshot";
    if (valid && read) append(reply,read(context));
    const size_t expected=measureJson(reply);
    if (reply.overflowed() || !expected || expected>=capacity || expected>=kMinOutput) return Result::Unavailable;
    const size_t written=serializeJson(reply,output,capacity);
    if (written!=expected || written>=capacity) { output[0]=0; return Result::Unavailable; }
    output[written]=0; used=written; return Result::Handled;
}
} // namespace brightnessRuntimeStatusProtocol
