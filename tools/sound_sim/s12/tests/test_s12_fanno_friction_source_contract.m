function tests = test_s12_fanno_friction_source_contract
%TEST_S12_FANNO_FRICTION_SOURCE_CONTRACT Specify exact Darcy source updates.
tests = functiontests(localfunctions);
end

function setupOnce(testCase)
addFannoPath(testCase);
end

function testForwardAndReverseFlowFollowExactDarcyDecay(testCase)
if ~requireFunction(testCase, "s12_fanno_exact_friction_step"); return; end
gamma = 1.4;
fDarcy = 0.02;
diameter = 0.10;
dt = 0.015;
for velocity = [3.0, -3.0]
    state = primitiveToConservative(2.0, velocity, 5.0, gamma);
    [next, diagnostics] = s12_fanno_exact_friction_step( ...
        state, gamma, fDarcy, diameter, dt);
    expectedVelocity = velocity / (1 + fDarcy / (2 * diameter) * ...
        abs(velocity) * dt);
    [rho, u, p] = primitive(next, gamma);
    verifyEqual(testCase, rho, 2.0, "AbsTol", 32 * eps);
    verifyEqual(testCase, u, expectedVelocity, "AbsTol", 32 * eps);
    verifyEqual(testCase, next(3), state(3), "AbsTol", 32 * eps);
    verifyGreaterThanOrEqual(testCase, p, 5.0);
    verifyEqual(testCase, sign(u), sign(velocity));
    verifyLessThanOrEqual(testCase, abs(u), abs(velocity));
    verifyEqual(testCase, diagnostics.friction_convention, "darcy");
end
end

function testZeroFrictionIsStrictNoOpAndHalfStepsCompose(testCase)
if ~requireFunction(testCase, "s12_fanno_exact_friction_step"); return; end
gamma = 1.4;
state = primitiveToConservative(1.2, 4.0, 2.5, gamma);
[zero, zeroDiagnostics] = s12_fanno_exact_friction_step( ...
    state, gamma, 0, 0.08, 0.1);
verifyEqual(testCase, zero, state, "AbsTol", 0, "RelTol", 0);
verifyEqual(testCase, zeroDiagnostics.source_applied, false);

[whole, ~] = s12_fanno_exact_friction_step(state, gamma, 0.04, 0.08, 0.1);
[half, ~] = s12_fanno_exact_friction_step(state, gamma, 0.04, 0.08, 0.05);
[twoHalf, ~] = s12_fanno_exact_friction_step(half, gamma, 0.04, 0.08, 0.05);
verifyEqual(testCase, twoHalf, whole, "AbsTol", 2e-14, "RelTol", 2e-14);
end

function testRejectsIllegalSourceInputs(testCase)
if ~requireFunction(testCase, "s12_fanno_exact_friction_step"); return; end
state = primitiveToConservative(1.0, 1.0, 1.0, 1.4);
verifyError(testCase, @() s12_fanno_exact_friction_step(state, 1, 0.02, 0.1, 0.1), ...
    "S12:Fanno:InvalidInput");
verifyError(testCase, @() s12_fanno_exact_friction_step(state, 1.4, -0.02, 0.1, 0.1), ...
    "S12:Fanno:InvalidInput");
verifyError(testCase, @() s12_fanno_exact_friction_step(state, 1.4, 0.02, 0, 0.1), ...
    "S12:Fanno:InvalidInput");
verifyError(testCase, @() s12_fanno_exact_friction_step(state, 1.4, 0.02, 0.1, -0.1), ...
    "S12:Fanno:InvalidInput");
end

function addFannoPath(testCase)
s12Root = fileparts(fileparts(mfilename("fullpath")));
fannoRoot = fullfile(s12Root, "validation", "fanno");
addpath(fannoRoot);
testCase.addTeardown(@() rmpath(fannoRoot));
end

function exists = requireFunction(testCase, name)
exists = exist(name, "file") == 2;
verifyTrue(testCase, exists, ...
    "Sprint 4B production function must exist: " + name);
end

function state = primitiveToConservative(rho, velocity, pressure, gamma)
state = [rho; rho * velocity; pressure / (gamma - 1) + 0.5 * rho * velocity^2];
end

function [rho, velocity, pressure] = primitive(state, gamma)
rho = state(1);
velocity = state(2) / rho;
pressure = (gamma - 1) * (state(3) - 0.5 * rho * velocity^2);
end
