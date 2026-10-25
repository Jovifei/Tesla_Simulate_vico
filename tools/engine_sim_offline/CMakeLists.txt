cmake_minimum_required(VERSION 3.20)
project(vico_engine_sim_offline LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_library(solver_core STATIC
 solver/src/rigid_body_system.cpp
 solver/src/matrix.cpp
 solver/src/system_state.cpp
 solver/src/utilities.cpp
 solver/src/ode_solver.cpp
 solver/src/euler_ode_solver.cpp
 solver/src/rk4_ode_solver.cpp
 solver/src/constraint.cpp
 solver/src/force_generator.cpp
 solver/src/rigid_body.cpp
 solver/src/sle_solver.cpp
 solver/src/gauss_seidel_sle_solver.cpp
 solver/src/fixed_position_constraint.cpp
 solver/src/static_force_generator.cpp
 solver/src/gravity_force_generator.cpp
 solver/src/link_constraint.cpp
 solver/src/gaussian_elimination_sle_solver.cpp
 solver/src/spring.cpp
 solver/src/line_constraint.cpp
 solver/src/constant_speed_motor.cpp
 solver/src/rolling_constraint.cpp
 solver/src/sparse_matrix.cpp
 solver/src/constant_rotation_constraint.cpp
 solver/src/nsv_ode_solver.cpp
 solver/src/generic_rigid_body_system.cpp
 solver/src/optimized_nsv_rigid_body_system.cpp
 solver/src/clutch_constraint.cpp
 solver/src/conjugate_gradient_sle_solver.cpp
 solver/src/rotation_friction_constraint.cpp
)
target_include_directories(solver_core PUBLIC solver/include)
add_library(engine_core STATIC
 upstream/src/audio_buffer.cpp
 upstream/src/camshaft.cpp
 upstream/src/crankshaft.cpp
 upstream/src/combustion_chamber.cpp
 upstream/src/connecting_rod.cpp
 upstream/src/convolution_filter.cpp
 upstream/src/cylinder_bank.cpp
 upstream/src/cylinder_head.cpp
 upstream/src/delay_filter.cpp
 upstream/src/derivative_filter.cpp
 upstream/src/direct_throttle_linkage.cpp
 upstream/src/dynamometer.cpp
 upstream/src/engine.cpp
 upstream/src/exhaust_system.cpp
 upstream/src/feedback_comb_filter.cpp
 upstream/src/filter.cpp
 upstream/src/fuel.cpp
 upstream/src/function.cpp
 upstream/src/gas_system.cpp
 upstream/src/gaussian_filter.cpp
 upstream/src/governor.cpp
 upstream/src/ignition_module.cpp
 upstream/src/impulse_response.cpp
 upstream/src/intake.cpp
 upstream/src/jitter_filter.cpp
 upstream/src/leveling_filter.cpp
 upstream/src/low_pass_filter.cpp
 upstream/src/part.cpp
 upstream/src/piston.cpp
 upstream/src/piston_engine_simulator.cpp
 upstream/src/simulator.cpp
 upstream/src/standard_valvetrain.cpp
 upstream/src/starter_motor.cpp
 upstream/src/synthesizer.cpp
 upstream/src/throttle.cpp
 upstream/src/transmission.cpp
 upstream/src/utilities.cpp
 upstream/src/valvetrain.cpp
 upstream/src/vehicle.cpp
 upstream/src/vehicle_drag_constraint.cpp
 upstream/src/vtec_valvetrain.cpp
)
target_include_directories(engine_core PUBLIC upstream/include)
target_link_libraries(engine_core PUBLIC solver_core)
target_compile_definitions(engine_core PRIVATE _CRT_SECURE_NO_WARNINGS)
add_executable(engine_offline offline_main.cpp model_builder.cpp)
target_link_libraries(engine_offline PRIVATE engine_core)
