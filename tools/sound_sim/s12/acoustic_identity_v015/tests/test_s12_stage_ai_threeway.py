"""Original rich A/B/C rendering, eight-car navigation and no fixed-recipe B."""
from pathlib import Path
import json
import subprocess
import shutil

import numpy as np
import pytest
from scipy.io import wavfile
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import three_way_audition as ui
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah import qualified_three_way as qualified
from tools.sound_sim.s12.acoustic_identity_v015.stage_ah.feedback_evidence import SCENES, sha_file


@pytest.fixture
def old_package(tmp_path,monkeypatch):
    specs=[]
    for vi,v in enumerate(qualified.VEHICLES):
        root=tmp_path/'sources'/v;web=root/'web_audio';web.mkdir(parents=True)
        scenes=[]
        for i,s in enumerate(SCENES):
            t=np.arange(4800)/48000.
            wave=(7000*np.sin(2*np.pi*(200+vi*40+i)*t)).astype(np.int16)
            ref=(8000*np.sin(2*np.pi*(350+vi*40+i)*t)).astype(np.int16)
            wavfile.write(web/(s+'.wav'),48000,wave);wavfile.write(web/('ref_'+s+'.wav'),48000,ref)
            scenes.append({'id':s,'index':i+1,'title':s,'desc':'controlled fixture','focus':'test',
                           'category':'cruise','candidate_file':s+'.wav','ref_file':'ref_'+s+'.wav'})
        page=root/'input.html';page.write_text('const SCENES='+json.dumps(scenes)+';',encoding='utf-8')
        # Intentional old fixed recipe with B == A: new UI must not call it auto.
        specs.append({'key':v,'name':v,'icon':'','title':v,'subtitle':'legacy fixture',
            'original':root,'feedback':root,'reference':root,'page':page,'status':'READY'})
    monkeypatch.setattr(ui,'_specs',lambda:specs)
    out=tmp_path/'old';ui.build_package(out)
    return out


def test_all_eight_preserve_ac_but_fixed_recipes_cannot_be_b(old_package,tmp_path):
    out=tmp_path/'qualified-abc'
    result=qualified.build(old_package,sha_file(old_package/'ARTIFACTS.json'),out)
    qualified.verify(out,sha_file(out/'ARTIFACTS.json'))
    for v,row in result['vehicles'].items():
        assert not row['source_roles']['feedback']['available']
        assert row['source_roles']['original']['available']
        assert row['source_roles']['reference']['available']
        for s in SCENES:
            for role in ('A','C'):
                name=role+'_'+s+'.wav'
                assert (old_package/v/'web_audio'/name).read_bytes()==(out/v/'web_audio'/name).read_bytes()
            assert not (out/v/'web_audio'/('B_'+s+'.wav')).exists()
        text=(out/v/'index.html').read_text(encoding='utf-8')
        assert '实时动态声学分析仪' in text and 'vehicleSwitcher' in text
        assert all('../'+car+'/index.html' in text for car in qualified.VEHICLES)
        assert 'audioEl.removeAttribute' in text
    # Same-schema metadata corruption can no longer pass verification.
    path=out/'hellcat'/'index.html';path.write_text(path.read_text(encoding='utf-8')+'tampered',encoding='utf-8')
    with pytest.raises(ValueError):qualified.verify(out)


def test_unavailable_source_switch_stops_stale_audio(old_package,tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node required for actual JavaScript state transition check')
    template=ui.TEMPLATE_PATH.read_text(encoding='utf-8')
    scenes=[{'id':'scene','title':'x','desc':'x','category':'idle','candidate_file':'A.wav','ref_file':''}]
    contract={'source_roles':{'original':{'available':True},'feedback':{'available':False},'reference':{'available':False}},
              'feedback_evidence':{'kind':'NO_QUALIFIED_AUTOMATIC_B'}}
    contract['source_roles']['feedback']['reason']='blocked'
    page=qualified.rich_page(template,'hellcat','test',scenes,contract,{},[],None)
    script=page.split('<script>\nconst TRIWAY_ROLES',1)[1].split('</script>',1)[0]
    script='const TRIWAY_ROLES'+script
    harness="""
let paused=false, removed=false, loaded=false;
let isPlaying=true,currentSceneIndex=0,currentSource='candidate',playbackSpeed=1,isLooping=false;
const SCENES=[{id:'scene'}],AUDIO_STORE={},DASHBOARD_CONTRACT={source_roles:{feedback:{available:false}}};
const audioEl={currentTime:2,pause(){paused=true},removeAttribute(){removed=true},load(){loaded=true}};
let renderSceneCards=()=>{},loadScene,changeScene,selectAndPlayScene;
const document={querySelectorAll(){return []},getElementById(){return null}};
const window={addEventListener(){}};
"""+script+"""
triSetAudio('feedback',false);
if(!paused||!removed||!loaded||isPlaying)throw new Error('stale audio remained active');
"""
    run=subprocess.run([node,'-e',harness],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
