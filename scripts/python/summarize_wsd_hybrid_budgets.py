"""Budget scenarios from measured strata; predictions are explicitly hypothetical."""
import json,math,hashlib
from pathlib import Path

def main():
    src=Path('outputs/reports/COMPARE_wsd_hybrid_routes_20260909.json');raw=src.read_bytes();r=json.loads(raw)
    hist=r['target_count_strata'];sample=r['sample_metrics'];total=r['totals'];speed=5394/319.887
    order=sorted(hist,key=lambda k:-(hist[k]['characters']/hist[k]['requests'])/sample[k]['mean_cost_usd'])
    options=[]
    for budget in (10,30,100):
        remaining=budget;counts={'requests':0,'targets':0.,'characters':0.,'eojeol':0.};parts=[]
        for cat in order:
            cost=sample[cat]['mean_cost_usd']*1.2;n=min(hist[cat]['requests'],math.floor((remaining+1e-12)/cost))
            remaining-=n*cost;counts['requests']+=n
            for k in ('targets','characters','eojeol'):counts[k]+=hist[cat][k]*n/hist[cat]['requests']
            parts.append({'category':cat,'requests':n,'estimated_usd':n*cost})
        scenarios=[]
        for p in (0,.5,.8,1):
            saved=counts['characters']*p;words=counts['eojeol']*p
            scenarios.append({'whole_request_clearance_assumption':p,'bareun_chars_reduction_pct':saved/total['characters']*100,'bareun_eojeol_reduction_pct':words/total['eojeol']*100,'bareun_days_saved_historical_speed':saved/speed/86400,'bareun_days_remaining_historical_speed':(total['characters']-saved)/speed/86400,'bareun_days_saved_at_hypothetical_100_chars_sec':saved/100/86400,'bareun_cost_value_saved_at_0_0025_krw_per_eojeol':words*.0025,'bareun_cost_value_saved_at_0_025_krw_per_eojeol':words*.025})
        options.append({'luna_budget_usd':budget,'budget_krw_at_assumed_1500':budget*1500,'estimated_usd':budget-remaining,'estimated_selected_volume':counts,'stratum_allocation':parts,'scenarios':scenarios})
    result={'schema':'wsd_hybrid_budget_scenarios.v1','api_called':False,'source_report_sha256':hashlib.sha256(raw).hexdigest(),'bareun_common_request_totals':total,'baseline_historical_speed_days':total['characters']/speed/86400,'baseline_at_hypothetical_100_chars_sec_days':total['characters']/100/86400,'bareun_full_eojeol_value_at_0_0025_won':total['eojeol']*.0025,'bareun_full_eojeol_value_at_0_025_won':total['eojeol']*.025,'luna_first':options,'luna_after':{'budget_options_usd':[10,30],'initial_bareun_volume_reduction':0,'remaining_volume_unknown':True,'full_resolution_not_guaranteed':True},'limitations':['Common 220-character core plus one utterance each side, not the only possible request design.','Within-stratum averages project a future random selection; no actual selected request list, model response, or semantic evaluation.','Complete usable group-decision rate is hypothetical; model correctness has not been tested. Errors cannot be treated as legitimate savings.','Luna wall time, API errors, retries, and local validation add time; savings here refer only to Bareun processing.','Both Bareun unit-price scenarios are conditional and are not verified account billing; existing allowance may make incremental cost zero.','KRW conversion uses a planning assumption, not a current exchange-rate quote. OpenAI tax and fees excluded.']}
    dest=Path('outputs/reports/COMPARE_wsd_hybrid_budgets_20260909.json')
    if dest.exists():raise FileExistsError(dest)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
