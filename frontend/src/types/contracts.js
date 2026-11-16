/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{id:number,job_id:number,title:string,status:string,round:number,snapshot:Object}} RectOrder */
/** @typedef {{id:number,order_id:number,title:string,assignee:string,status:string,note:string,evidence:string[],version:number}} RectMeasure */
/** @typedef {{id:number,order_id:number,round:number,assignee:string,status:string,result:Object}} RectPackage */
/** @typedef {{id:number,measure_id:number,kind:string,field:string,status:string,measure_version:number}} RectDispute */
export {};
