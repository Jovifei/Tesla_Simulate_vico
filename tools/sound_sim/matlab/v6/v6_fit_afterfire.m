function [profile, report] = v6_fit_afterfire(profile, referencePath)
%V6_FIT_AFTERFIRE Fit only identifiable C63 afterfire spectral gains.

arguments
    profile (1,1) struct
    referencePath (1,1) string
end

[referenceAudio, referenceRate] = audioread(referencePath);
reference = v6_reference_features(referenceAudio, referenceRate);
scenario = v6_build_cycle(profile, "tipout_5500", 1000);
crackCandidates = [0.40, 0.80, 1.20];
bodyCandidates = [0.60, 0.90, 1.20];
metalCandidates = [1.00, 1.80, 2.80];
bestError = inf;
best = profile.afterfire;
rows = cell(numel(crackCandidates) * numel(bodyCandidates) * numel(metalCandidates), 5);
rowIndex = 0;
for crack = crackCandidates
    for body = bodyCandidates
        for metal = metalCandidates
            candidate = profile;
            candidate.afterfire.crack_gain = crack;
            candidate.afterfire.body_gain = body;
            candidate.afterfire.metal_gain = metal;
            [~, result] = v6_synthesize_engine_sound(candidate, scenario);
            generated = v6_reference_features(result.layers.afterfire, ...
                candidate.audio.sample_rate_hz);
            errorValue = feature_error(generated, reference);
            rowIndex = rowIndex + 1;
            rows(rowIndex, :) = {crack, body, metal, errorValue, generated.centroid_hz};
            if errorValue < bestError
                bestError = errorValue;
                best = candidate.afterfire;
            end
        end
    end
end
profile.afterfire = best;

bodyDecayCandidates = [0.025, 0.040, 0.060];
metalDecayCandidates = [0.018, 0.035, 0.050];
decayRows = cell(numel(bodyDecayCandidates) * numel(metalDecayCandidates), 4);
decayRowIndex = 0;
for bodyDecay = bodyDecayCandidates
    for metalDecay = metalDecayCandidates
        candidate = profile;
        candidate.afterfire.body_decay_s = bodyDecay;
        candidate.afterfire.metal_decay_s = metalDecay;
        [~, result] = v6_synthesize_engine_sound(candidate, scenario);
        generated = v6_reference_features(result.layers.afterfire, ...
            candidate.audio.sample_rate_hz);
        errorValue = feature_error(generated, reference);
        decayRowIndex = decayRowIndex + 1;
        decayRows(decayRowIndex, :) = {bodyDecay, metalDecay, errorValue, generated.centroid_hz};
        if errorValue < bestError
            bestError = errorValue;
            best = candidate.afterfire;
        end
    end
end
profile.afterfire = best;
report = struct();
report.reference_path = referencePath;
report.reference = reference;
report.best_error = bestError;
report.best_afterfire = best;
report.gain_candidates = cell2table(rows, VariableNames=["crack_gain", "body_gain", ...
    "metal_gain", "objective", "generated_centroid_hz"]);
report.decay_candidates = cell2table(decayRows, VariableNames=["body_decay_s", ...
    "metal_decay_s", "objective", "generated_centroid_hz"]);
end

function errorValue = feature_error(generated, reference)
centroidError = log((generated.centroid_hz + eps) / (reference.centroid_hz + eps))^2;
bandError = sum((generated.band_shares - reference.band_shares).^2);
flatnessError = (generated.flatness - reference.flatness)^2;
errorValue = 0.25 * centroidError + 0.65 * bandError + 0.10 * flatnessError;
end
