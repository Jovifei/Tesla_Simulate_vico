#ifndef VICO_OFFLINE_MODEL_BUILDER_H
#define VICO_OFFLINE_MODEL_BUILDER_H

#include "upstream/include/engine.h"

#include <memory>

// Frozen generic research model derived from upstream 07_gm_ls.mr.
// This is not a Hellcat model or a claim of OEM acoustic/engineering accuracy.
struct OfflineModel {
    Engine engine;

    // Construction does not allocate the Function/camshaft configuration.
    OfflineModel();
    ~OfflineModel();
    OfflineModel(const OfflineModel &) = delete;
    OfflineModel &operator=(const OfflineModel &) = delete;

    void initialize();

    // Release the Simulator before destroying this model: it refers to these parts.
    void destroy();
    bool initialized() const noexcept { return engineInitialized_; }

private:
    struct Resources;
    std::unique_ptr<Resources> resources_;
    bool engineInitialized_ = false;
};

#endif
