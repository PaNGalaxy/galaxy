define(function(){function e(e){e+="";for(var t=/(\d+)(\d{3})/;t.test(e);)e=e.replace(t,"$1,$2");return e}return{commatize:e,is_deferred:function(e){return"promise"in e},ServerStateDeferred:Backbone.Model.extend({defaults:{ajax_settings:{},interval:1e3,success_fn:function(e){return!0}},go:function(){var e=$.Deferred(),t=this,n=t.get("ajax_settings"),r=t.get("success_fn"),a=t.get("interval"),i=function(){$.ajax(n).success(function(t){r(t)?e.resolve(t):setTimeout(i,a)})};return i(),e}}),get_random_color:function(e){e||(e="#ffffff"),"string"==typeof e&&(e=[e]);for(var t=0;t<e.length;t++)e[t]=parseInt(e[t].slice(1),16);var n,r,a,i,f,o,s,u,c,d,h,m=function(e,t,n){return(299*e+587*t+114*n)/1e3},g=!1,l=0;do{for(n=Math.round(16777215*Math.random()),r=(16711680&n)>>16,a=(65280&n)>>8,i=255&n,c=m(r,a,i),g=!0,t=0;t<e.length;t++)if(f=e[t],o=(16711680&f)>>16,s=(65280&f)>>8,u=255&f,d=m(o,s,u),h=function(e,t,n,r,a,i){return Math.max(e,r)-Math.min(e,r)+(Math.max(t,a)-Math.min(t,a))+(Math.max(n,i)-Math.min(n,i))}(r,a,i,o,s,u),Math.abs(c-d)<40||h<200){g=!1;break}l++}while(!g&&l<=10);return"#"+(16777216+n).toString(16).substr(1,6)}}});
//# sourceMappingURL=../../../maps/viz/trackster/util.js.map
