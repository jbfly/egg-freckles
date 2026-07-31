10 FUNCTION svc() {label:"inet",type:'service,opCode:512,result:nil}
20 FUNCTION ldata(id) {arglist:[id],typeList:['struct,'ulong]}
30 FUNCTION lid(id) {label:"ilid",type:'option,opCode:512,result:nil,form:'template,data:U:ldata(id)}
40 FUNCTION vdata() {arglist:[1],typeList:['struct,'ulong]}
50 FUNCTION ver() {label:"itsv",type:'option,opCode:512,result:nil,form:'template,data:U:vdata()}
60 FUNCTION opts(id) BEGIN LOCAL a,b,c;a:=U:svc();b:=U:lid(id);c:=U:ver();[a,b,c] END
70 FUNCTION adata() {arglist:[10,42,0,1,18081],typelist:['struct,'byte,'byte,'byte,'byte,'short]}
80 FUNCTION addr() [{label:"itrs",type:'option,opCode:512,result:nil,form:'template,data:U:adata()}]
90 FUNCTION suck(a) GetDefaultStore():SuckPackageFromBinary(a,nil)
100 FUNCTION install(d) begin ClearVBOCache(d);AddDelayedCall(U.suck,[d],1000) end
110 FUNCTION got(ep,d,t,o) if t and t.condition='byteCount and t.byteCount=15000 then U:install(d)
120 FUNCTION vbo() GetDefaultStore():NewVBO('package,15000)
130 FUNCTION term() {byteCount:15000}
140 FUNCTION spec(v) {form:'binary,target:{data:v,offset:0},termination:U:term(),discardAfter:15000,InputScript:U.got}
150 FUNCTION ep() {_proto:@383,_parent:U}
155 FUNCTION err() call GetGlobalFn('InetGetExceptionError) with (CurrentException())
160 FUNCTION setup(id) try begin U.e:=U:ep();U.e:Instantiate(U.e,U:opts(id));U.e:Bind(nil,{async:nil,reqTimeout:10000});'ok end onexception |evt.ex| do U:err()
170 FUNCTION conn() U.e:connect(U:addr(),{async:nil,reqTimeout:45000})
180 FUNCTION listen() U.e:SetInputSpec(U:spec(U:vbo()))
190 FUNCTION send() U.e:output("G",nil,{form:'string,async:nil,reqTimeout:10000})
200 FUNCTION start(id) begin U:setup(id);U:conn();U:listen();U:send();true end
210 FUNCTION grab(id,s,x) begin U.gid:=id;if x or U.e or s.linkStatus <> 'connected then nil else U:start(id) end
220 FUNCTION go() call GetGlobalFn('InetGrabLink) with (nil,U,'grab)
230 LET e=NIL
240 U:go()
250 WAIT 60000
300 FUNCTION svc() {label:"inet",type:'service,opCode:512,result:nil}
