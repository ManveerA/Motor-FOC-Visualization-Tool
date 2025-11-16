% 2025-10-12
% Real-Time Hands-on Tool for Teaching Three-Phase Motor Control

close all; clear; clc;

%% Internal Motor Mechanical Parameters 

p = 5;         % Pole-pairs
lambda = 0.04; % Flux linkage

%% Motor Electrical Parameters 

Rs = 12E-3; % Stator resistance per phase
L = 240E-6; % Stator inductance per phase
Ld = L;     % d-axis inductance
Lq = L;     % q-axis inductance

Vdc = 800;   % DC-link voltage
f_sw = 20E3; % Inverter switching frequency

%% External Motor Mechanical Parameters 

J_m = 1.125;        % Moment of inertia
T_rr = 3.969;       % Rolling resistance constant
K_d = 9.115875E-06; % Drag constant

%% Torque Controller (Inner Loop)

K_ii = 2.503252558704921; % Torque controller integral term
K_pi = 0.250325255870492; % Torque controller proportional term

%% Speed Controller (Outer Loop)

K_is = 0.151446889233266; % Speed controller integral term
K_ps = 1.514468892332664; % Speed controller proportional term

%% Saturation Limits

T_max = 140;   % Maximum torque
V_max = Vdc/2; % Maximum inverter voltage (peak amplitude per phase)