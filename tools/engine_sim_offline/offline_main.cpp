#include "model_builder.h"
#include "offline_taps.h"
#include "upstream/include/simulator.h"
#include "upstream/include/units.h"
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace offline {
void (*source)(Engine *, const double *, int) = nullptr;
void (*audio)(float, float, float, float, float, float) = nullptr;
}
namespace {
constexpr int physicsFs=10000, audioFs=44100, seed=24817;
constexpr double dt=1.0/physicsFs, blockSeconds=.01, warmupSeconds=5;
std::ofstream pressures,states,audioTaps;
bool recording=false;
uint64_t sourceFrames=0,audioFrames=0,clipCount=0,litCylinderSteps=0;
double cycles=0,cycleOrigin=0,target=910,command=.08,minRpm=1e30,maxRpm=0,maxAudio=0,minOmega=1e30,maxOmega=-1e30;
std::pair<double,double> control(const std::string &s,double t){
 if(s=="high")return {5000,.70};
 if(s=="low"||s=="smoke")return {910,.08};
 if(s=="main"){
  if(t<15)return {910,.08};
  if(t<30){double a=(t-15)/15;return {910+4090*a,.08+.62*a};}
  if(t<45)return {5000,.70};
  if(t<55)return {5000-4090*(t-45)/10,.015};
  return {910,.08};
 }
 if(s=="holdout"){
  if(t<10)return {1200,.12};
  if(t<22){double a=(t-10)/12;return {1200+2300*a,.12+.43*a};}
  if(t<35)return {3500,.55};
  if(t<43)return {3500-2000*(t-35)/8,.02};
  if(t<50)return {1500,.16};
  if(t<56)return {1500+2800*(t-50)/6,.60};
  return {4300-3390*(t-56)/4,.015};
 }
 throw std::runtime_error("Unknown scene");
}
void sourceTap(Engine *e,const double *input,int groups){
 cycles+=e->getSpeed()*dt/(4*constants::pi);
 if(!recording)return;
 if(groups!=2||e->getCylinderCount()!=8)throw std::runtime_error("Unexpected source schema");
 std::array<float,18> row{};
 for(int i=0;i<8;++i){row[i]=float(e->getChamber(i)->m_system.pressure());row[8+i]=float(e->getChamber(i)->m_exhaustRunnerAndPrimary.pressure());litCylinderSteps+=e->getChamber(i)->isLit();}
 row[16]=float(input[0]);row[17]=float(input[1]);
 for(float x:row)if(!std::isfinite(x))throw std::runtime_error("Nonfinite physical capture");
 pressures.write(reinterpret_cast<const char*>(row.data()),sizeof(row));++sourceFrames;
 minRpm=std::min(minRpm,e->getRpm());maxRpm=std::max(maxRpm,e->getRpm());
 double omega=e->getOutputCrankshaft()->m_body.v_theta;minOmega=std::min(minOmega,omega);maxOmega=std::max(maxOmega,omega);
 if(sourceFrames%100==0)states<<(sourceFrames-1)*dt<<','<<e->getRpm()<<','<<target<<','<<command<<','<<e->getThrottle()<<','<<e->getManifoldPressure()<<','<<e->getOutputCrankshaft()->getCycleAngle()<<','<<cycles-cycleOrigin<<'\n';
}
void audioTap(float raw,float post,float leveled,float output,float gain,float clipped){
 if(!recording)return;
 std::array<float,6> row{raw,post,leveled,output,gain,clipped};
 for(float x:row)if(!std::isfinite(x))throw std::runtime_error("Nonfinite audio capture");
 audioTaps.write(reinterpret_cast<const char*>(row.data()),sizeof(row));++audioFrames;clipCount+=clipped!=0;
 maxAudio=std::max(maxAudio,double(std::abs(output)));
}
}
int main(int argc,char **argv){
 if(argc!=4){std::cerr<<"engine_offline NEW_DIR main|low|high|holdout|smoke seconds\n";return 2;}
 try{
  std::filesystem::path out(argv[1]);std::string scene(argv[2]);double seconds=std::stod(argv[3]);
  if(!(seconds>0&&seconds<=60)||std::filesystem::exists(out))throw std::runtime_error("Invalid duration or output exists");
  std::filesystem::create_directories(out);
  pressures.open(out/"pressure-input.f32le",std::ios::binary);audioTaps.open(out/"audio-taps.f32le",std::ios::binary);
  states.open(out/"state.csv");states<<std::setprecision(14)<<"t_s,rpm,target_rpm,speed_control,throttle_plate,map_pa,cycle_angle_rad,integrated_cycles\n";
  std::ofstream torque(out/"dyno.csv");torque<<std::setprecision(14)<<"t_s,torque_nm\n";
  std::srand(seed);OfflineModel model;model.initialize();Engine *e=&model.engine;
  Vehicle vehicle;Vehicle::Parameters vp{1600,.3,2,3.42,.33,200};vehicle.initialize(vp);
  double gears[]={3,2,1};Transmission transmission;Transmission::Parameters tp{3,gears,1000};transmission.initialize(tp);transmission.setClutchPressure(0);
  std::unique_ptr<Simulator> sim(e->createSimulator(&vehicle,&transmission));
  sim->setSimulationFrequency(physicsFs);sim->setSimulationSpeed(1);sim->m_dyno.m_enabled=false;sim->m_dyno.m_hold=true;e->getIgnitionModule()->m_enabled=true;
  auto &synth=sim->synthesizer();synth.m_run=false;
  const int16_t identityIR[]={32767};for(int i=0;i<2;++i)synth.initializeImpulseResponse(identityIR,1,1,i);
  auto ap=synth.getAudioParameters();std::vector<int16_t> drain(44100);synth.readAudioOutput(44100,drain.data());
  offline::source=sourceTap;offline::audio=audioTap;
  auto started=std::chrono::steady_clock::now();int frames=int(std::llround((warmupSeconds+seconds)/blockSeconds));uint64_t allSteps=0;
  for(int frame=0;frame<frames;++frame){
   double t=frame*blockSeconds-warmupSeconds;auto c=control(scene,std::max(0.0,t));target=c.first;command=c.second;
   e->setSpeedControl(command);sim->m_dyno.m_rotationSpeed=units::rpm(target);
   // Match the original GUI's starter direction before engaging the hold dyno.
   // Starting the bidirectional dyno at rest selects reverse rotation instead.
   sim->m_starterMotor.m_enabled=frame<50;
   if(frame==50){
    if(e->getOutputCrankshaft()->m_body.v_theta>=0)throw std::runtime_error("Starter failed to establish CW rotation");
    sim->m_dyno.m_enabled=true;
   }
   if(frame==int(warmupSeconds/blockSeconds)){recording=true;cycleOrigin=cycles;}
   sim->startFrame(blockSeconds);while(sim->simulateStep())++allSteps;
   sim->endFrame();synth.renderAudio();int got=synth.readAudioOutput(2000,drain.data());if(got<=0)throw std::runtime_error("No audio output");
   if(recording)torque<<(frame+1)*blockSeconds-warmupSeconds<<','<<sim->getFilteredDynoTorque()<<'\n';
   if((frame+1)%1000==0)std::cout<<"simulated_s="<<(frame+1)*blockSeconds<<" rpm="<<e->getRpm()<<" audio_frames="<<audioFrames<<std::endl;
  }
  double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
  pressures.close();audioTaps.close();states.close();torque.close();
  std::ofstream r(out/"capture.json");r<<std::setprecision(15)<<"{\n\"model\":\"generic_crossplane_v8_ls_example_NOT_HELLCAT\",\n\"scene\":\""<<scene<<"\",\"duration_s\":"<<seconds<<",\"warmup_s\":"<<warmupSeconds<<",\"seed\":"<<seed<<",\"physics_fs\":"<<physicsFs<<",\"audio_fs\":"<<audioFs<<",\"physics_frames\":"<<sourceFrames<<",\"all_steps\":"<<allSteps<<",\"audio_frames\":"<<audioFrames<<",\"wall_s\":"<<wall<<",\"min_rpm\":"<<minRpm<<",\"max_rpm\":"<<maxRpm<<",\"final_peak\":"<<maxAudio<<",\"clip_count\":"<<clipCount<<",\"dsp\":{\"volume\":"<<ap.volume<<",\"jitter\":"<<ap.inputSampleNoise<<",\"air_noise\":"<<ap.airNoise<<",\"derivative_mix\":"<<ap.dF_F_mix<<",\"leveler_target\":"<<ap.levelerTarget<<",\"ir\":\"analytic_identity\"},\"qualification\":\"OFFLINE_SYNTHETIC_MECHANISM_ONLY\"}\n";
  std::ofstream validity(out/"physical-validity.json");validity<<std::setprecision(15)<<"{\"initialization\":\"upstream_starter0.5s_then_hold_dyno\",\"min_omega_rad_s\":"<<minOmega<<",\"max_omega_rad_s\":"<<maxOmega<<",\"lit_cylinder_steps\":"<<litCylinderSteps<<",\"cw_all_capture\":"<<(maxOmega<0?"true":"false")<<"}\n";
  offline::source=nullptr;offline::audio=nullptr;sim->Simulator::destroy();sim->destroy();sim.reset();model.destroy();
  std::cout<<"CAPTURE_COMPLETE "<<out.string()<<" wall_s="<<wall<<std::endl;
  return sourceFrames==uint64_t(std::llround(seconds*physicsFs))?0:3;
 }catch(const std::exception&e){std::cerr<<"CAPTURE_FAILED: "<<e.what()<<std::endl;return 1;}
}
