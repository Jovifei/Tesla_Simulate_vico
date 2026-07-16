function tests = test_s12_transient_wave_boundary_contract
%TEST_S12_TRANSIENT_WAVE_BOUNDARY_CONTRACT Specify validation-only ghosts.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
transientRoot = fullfile(s12Root, "validation", "transient_wave");
if isfolder(transientRoot)
    addpath(transientRoot);
    testCase.addTeardown(@() rmpath(transientRoot));
end
end

function testUniformStateIsFixedPointForEveryBoundary(testCase)
if ~requireFunction(testCase, "s12_transient_wave_boundary_state"); return; end
gamma = 1.4;
ambientPressure = 101325;
state = primitiveToConservative(1.2, 0, ambientPressure, gamma);
for side = ["left", "right"]
    for boundaryType = ["closed_rigid_end", ...
            "ideal_pressure_release_open_end", "nonreflecting_reference_boundary"]
        result = s12_transient_wave_boundary_state(state, state, gamma, ...
            side, boundaryType);
        verifyEqual(testCase, result.state, state, "AbsTol", 32 * eps);
        verifyEqual(testCase, result.boundary_type, boundaryType);
    end
end
end

function testClosedAndOpenEndsPreserveTheirFrozenReflectionSigns(testCase)
if ~requireFunction(testCase, "s12_transient_wave_boundary_state"); return; end
gamma = 1.4;
ambientPressure = 101325;
state = primitiveToConservative(1.22, 4.0, 101425, gamma);
ambient = primitiveToConservative(1.2, 0, ambientPressure, gamma);
closed = s12_transient_wave_boundary_state(state, ambient, gamma, ...
    "right", "closed_rigid_end");
[rho, velocity, pressure] = primitive(state, gamma);
[closedRho, closedVelocity, closedPressure] = primitive(closed.state, gamma);
verifyEqual(testCase, closedRho, rho, "RelTol", 32 * eps);
verifyEqual(testCase, closedPressure, pressure, "RelTol", 32 * eps);
verifyEqual(testCase, closedVelocity, -velocity, "RelTol", 32 * eps);

open = s12_transient_wave_boundary_state(state, ambient, gamma, ...
    "right", "ideal_pressure_release_open_end");
[~, ~, openPressure] = primitive(open.state, gamma);
verifyEqual(testCase, openPressure, ambientPressure, "RelTol", 32 * eps);
verifyEqual(testCase, open.outgoing_characteristic, ...
    characteristic(state, gamma, "right", "outgoing"), "RelTol", 2e-13);
verifyGreaterThan(testCase, open.state(1), 0);
end

function testNonreflectingBoundaryPreservesOutgoingAndSetsAmbientIncoming(testCase)
if ~requireFunction(testCase, "s12_transient_wave_boundary_state"); return; end
gamma = 1.4;
ambientPressure = 101325;
ambient = primitiveToConservative(1.2, 0, ambientPressure, gamma);
state = primitiveToConservative(1.21, 2.0, 101425, gamma);
result = s12_transient_wave_boundary_state(state, ambient, gamma, ...
    "right", "nonreflecting_reference_boundary");
verifyEqual(testCase, result.outgoing_characteristic, ...
    characteristic(state, gamma, "right", "outgoing"), "RelTol", 2e-13);
verifyEqual(testCase, result.incoming_characteristic, ...
    characteristic(ambient, gamma, "right", "incoming"), "RelTol", 2e-13);
verifyGreaterThan(testCase, result.state(1), 0);
verifyGreaterThan(testCase, primitive(result.state, gamma), 0);
end

function testBoundaryRejectsUnknownModeAndNonphysicalState(testCase)
if ~requireFunction(testCase, "s12_transient_wave_boundary_state"); return; end
state = primitiveToConservative(1.2, 0, 101325, 1.4);
verifyError(testCase, @() s12_transient_wave_boundary_state(state, state, 1.4, ...
    "right", "transmissive"), "S12:TransientWave:InvalidBoundary");
state(1) = -1;
ambient = primitiveToConservative(1.2, 0, 101325, 1.4);
verifyError(testCase, @() s12_transient_wave_boundary_state(state, ambient, 1.4, ...
    "right", "closed_rigid_end"), ...
    "S12:TransientWave:InvalidState");
end

function value = characteristic(state, gamma, side, kind)
[~, velocity, ~, soundSpeed] = primitive(state, gamma);
if side == "right"
    if kind == "outgoing"; value = velocity + 2 * soundSpeed / (gamma - 1); else; value = velocity - 2 * soundSpeed / (gamma - 1); end
else
    if kind == "outgoing"; value = velocity - 2 * soundSpeed / (gamma - 1); else; value = velocity + 2 * soundSpeed / (gamma - 1); end
end
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + 0.5 * rho * velocity^2];
end

function [rho, velocity, pressure, soundSpeed] = primitive(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
soundSpeed = sqrt(gamma * pressure / rho);
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4C production function must exist: " + name);
end
