import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const rectifications={
 list:()=>api('/rectifications'),
 get:id=>api('/rectifications/'+id),
 create:data=>api('/rectifications',{method:'POST',body:JSON.stringify(data)}),
 addMeasure:(id,data)=>api('/rectifications/'+id+'/measures',{method:'POST',body:JSON.stringify(data)}),
 patchMeasure:(id,mid,data)=>api('/rectifications/'+id+'/measures/'+mid,{method:'PATCH',body:JSON.stringify(data)}),
 claim:(id,assignee)=>api('/rectifications/'+id+'/packages',{method:'POST',body:JSON.stringify({assignee})}),
 getPackage:(id,pid)=>api('/rectifications/'+id+'/packages/'+pid),
 returnPackage:(id,pid,payload)=>api('/rectifications/'+id+'/packages/'+pid+'/return',{method:'POST',body:JSON.stringify({payload})}),
 resolve:(id,did,data)=>api('/rectifications/'+id+'/disputes/'+did+'/resolve',{method:'POST',body:JSON.stringify(data)}),
 accept:id=>api('/rectifications/'+id+'/accept',{method:'POST'}),
 sendBack:(id,note)=>api('/rectifications/'+id+'/send-back',{method:'POST',body:JSON.stringify({note})})
};
