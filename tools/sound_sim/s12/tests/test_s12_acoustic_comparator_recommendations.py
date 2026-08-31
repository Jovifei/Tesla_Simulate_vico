from tools.sound_sim.s12.acoustic_comparator.recommendations.recommendation_engine import recommend
def test_recommendations_exclude_protected_layers():
    r=recommend("afterfire_ineligible",{"wrong_condition_event_count":1})
    assert r["parameter_group"] == "state gate / event centroid / decay"
