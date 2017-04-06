define(["libs/underscore"],function(t){var e=function(t,e){var a=t[0],i=t[1],r=e[0],l=e[1];return a<r?i<=r?1001:i<=l?1003:1002:a>l?1006:i<=l?1005:1004},a=function(t,a){var i=e(t,a);return 1001!==i&&1006!==i},i=function(t,e,a,i,r,l){void 0===l&&(l=4);var n,s=i-e,o=r-a,h=Math.floor(Math.sqrt(s*s+o*o)/l),_=s/h,f=o/h;for(n=0;n<h;n++,e+=_,a+=f)n%2==0&&t.fillRect(e,a,l,1)},r=function(t,e,a,i){var r=e-i/2,l=e+i/2,n=a-Math.sqrt(3*i/2);t.beginPath(),t.moveTo(r,n),t.lineTo(l,n),t.lineTo(e,a),t.lineTo(r,n),t.strokeStyle=this.fillStyle,t.fill(),t.stroke(),t.closePath()},l=function(t){this.default_val=t||1};l.prototype.gen_val=function(t){return this.default_val};var n=function(t){this.incomplete_features=t.incomplete_features,this.feature_mapper=t.feature_mapper},s=function(e,a,i,r,l){this.data=e,this.view_start=a,this.view_end=i,this.prefs=t.extend({},this.default_prefs,r),this.mode=l};s.prototype.default_prefs={},s.prototype.draw=function(t,e,a,i){},s.prototype.get_start_draw_pos=function(t,e){return this._chrom_pos_to_draw_pos(t,e,-.5)},s.prototype.get_end_draw_pos=function(t,e){return this._chrom_pos_to_draw_pos(t,e,.5)},s.prototype.get_draw_pos=function(t,e){return this._chrom_pos_to_draw_pos(t,e,0)},s.prototype._chrom_pos_to_draw_pos=function(t,e,a){return Math.floor(e*(Math.max(0,t-this.view_start)+a))};var o=function(t,e,a,i,r){s.call(this,t,e,a,i,r)};o.prototype.default_prefs={min_value:void 0,max_value:void 0,mode:"Histogram",color:"#000",overflow_color:"#F66"},o.prototype.draw=function(e,a,i,r){var l=!1,n=this.prefs.min_value,s=this.prefs.max_value,o=s-n,h=i,_=this.view_start,f=this.mode,c=this.data;e.save();var u=Math.round(i+n/o*i);"Intensity"!==f&&(e.fillStyle="#aaa",e.fillRect(0,u,a,1)),e.beginPath();var p,d,g;g=c.length>1?t.map(c.slice(0,-1),function(t,e){return Math.ceil((c[e+1][0]-c[e][0])*r)}):[10];for(var v,m=this.prefs.block_color||this.prefs.color,w=parseInt(m.slice(1),16),y=(16711680&w)>>16,x=(65280&w)>>8,M=255&w,b=!1,S=!1,k=0,P=c.length;k<P;k++)if(e.fillStyle=e.strokeStyle=m,b=S=!1,v=g[k],p=Math.floor((c[k][0]-_-.5)*r),null!==(d=c[k][1])){if(d<n?(S=!0,d=n):d>s&&(b=!0,d=s),"Histogram"===f)d=Math.round(d/o*h),e.fillRect(p,u,v,-d);else if("Intensity"===f){var R=(d-n)/o,A=Math.round(y+(255-y)*(1-R)),F=Math.round(x+(255-x)*(1-R)),T=Math.round(M+(255-M)*(1-R));e.fillStyle="rgb("+A+","+F+","+T+")",e.fillRect(p,0,v,h)}else d=Math.round(h-(d-n)/o*h),l?e.lineTo(p,d):(l=!0,"Filled"===f?(e.moveTo(p,h),e.lineTo(p,d)):e.moveTo(p,d));if(e.fillStyle=this.prefs.overflow_color,b||S){var I;"Histogram"===f||"Intensity"===f?I=v:(p-=2,I=4),b&&e.fillRect(p,0,I,3),S&&e.fillRect(p,h-3,I,3)}e.fillStyle=m}else l&&"Filled"===f&&e.lineTo(p,h),l=!1;"Filled"===f?(l&&(e.lineTo(p,u),e.lineTo(0,u)),e.fill()):e.stroke(),e.restore()};var h=function(t){this.feature_positions={},this.slot_height=t,this.translation=0,this.y_translation=0};h.prototype.map_feature_data=function(t,e,a,i){this.feature_positions[e]||(this.feature_positions[e]=[]),this.feature_positions[e].push({data:t,x_start:a,x_end:i})},h.prototype.get_feature_data=function(t,e){var a,i=Math.floor((e-this.y_translation)/this.slot_height);if(!this.feature_positions[i])return null;t+=this.translation;for(var r=0;r<this.feature_positions[i].length;r++)if(a=this.feature_positions[i][r],t>=a.x_start&&t<=a.x_end)return a.data};var _=function(t,e,a,i,r,n,o){s.call(this,t,e,a,i,r),this.alpha_scaler=n||new l,this.height_scaler=o||new l,this.max_label_length=200};_.prototype.default_prefs={block_color:"#FFF",connector_color:"#FFF"},t.extend(_.prototype,{get_required_height:function(t,e){var a=this.get_row_height(),i=a,r=this.mode;return"no_detail"!==r&&"Squish"!==r&&"Pack"!==r||(a=t*i),a+this.get_top_padding(e)},get_top_padding:function(t){return 0},draw:function(t,e,a,i,r){var l=this.data,s=this.view_start,o=this.view_end;t.save(),t.fillStyle=this.prefs.block_color,t.textAlign="right";for(var _,f=this.get_row_height(),c=new h(f),u=[],p=0,d=l.length;p<d;p++){var g=l[p],v=g[0],m=g[1],w=g[2],y=r&&void 0!==r[v]?r[v].slot:null;("Dense"===this.mode||null!==y)&&m<o&&w>s&&(_=this.draw_element(t,this.mode,g,y,s,o,i,f,e),c.map_feature_data(g,y,_[0],_[1]),(m<s||w>o)&&u.push(g))}return t.restore(),c.y_translation=this.get_top_padding(e),new n({incomplete_features:u,feature_mapper:c})},draw_element:function(t,e,a,i,r,l,n,s,o){return[0,0]}});var f=function(t,e,a,i,r,l,n){_.call(this,t,e,a,i,r,l,n),this.draw_background_connector=!0,this.draw_individual_connectors=!1};t.extend(f.prototype,_.prototype,{get_row_height:function(){var t=this.mode;return"Dense"===t?10:"no_detail"===t?3:"Squish"===t?5:10},draw_element:function(t,e,a,i,r,l,n,s,o){var h,_=(a[0],a[1]),f=a[2],c=a[3],u=a[4],p=Math.floor(Math.max(0,(_-r-.5)*n)),d=Math.ceil(Math.min(o,Math.max(0,(f-r-.5)*n))),g=p,v=d,h=("Dense"===e?0:0+i)*s+this.get_top_padding(o),m=null,w=null,y=u&&"+"!==u&&"."!==u?this.prefs.reverse_strand_color:this.prefs.block_color;if(label_color=this.prefs.label_color,t.globalAlpha=this.alpha_scaler.gen_val(a),"Dense"===e&&(i=1),"no_detail"===e)t.fillStyle=y,t.fillRect(p,h+5,d-p,1);else{var x=a[5],M=a[6],b=a[7],S=!0;x&&M&&(m=Math.floor(Math.max(0,(x-r)*n)),w=Math.ceil(Math.min(o,Math.max(0,(M-r)*n))));var k,P;if("Squish"===e?(k=1,P=3,S=!1):(k=5,P=9),b){var R,A;"Squish"===e||"Dense"===e?(R=h+Math.floor(1.5)+1,A=1):u?(R=h,A=P):(R+=2.5,A=1),this.draw_background_connector&&("Squish"===e||"Dense"===e?t.fillStyle="#ccc":u?"+"===u?t.fillStyle=t.canvas.manager.get_pattern("right_strand"):"-"===u&&(t.fillStyle=t.canvas.manager.get_pattern("left_strand")):t.fillStyle="#ccc",t.fillRect(p,R,d-p,A));for(var F=0,T=b.length;F<T;F++){var I,q,D=b[F],H=Math.floor(Math.max(0,(D[0]-r-.5)*n)),X=Math.ceil(Math.min(o,Math.max((D[1]-r-.5)*n)));if(!(H>X)){if(t.fillStyle=y,t.fillRect(H,h+(P-k)/2+1,X-H,k),void 0!==m&&M>x&&!(H>w||X<m)){var L=Math.max(H,m),N=Math.min(X,w);t.fillRect(L,h+1,N-L,P),1===b.length&&"Pack"===e&&("+"===u?t.fillStyle=t.canvas.manager.get_pattern("right_strand_inv"):"-"===u&&(t.fillStyle=t.canvas.manager.get_pattern("left_strand_inv")),L+14<N&&(L+=2,N-=2),t.fillRect(L,h+1,N-L,P))}this.draw_individual_connectors&&I&&this.draw_connector(t,I,q,H,X,h),I=H,q=X}}if("Pack"===e){t.globalAlpha=1,t.fillStyle="white";var O=this.height_scaler.gen_val(a),j=Math.ceil(P*O),C=Math.round((P-j)/2);1!==O&&(t.fillRect(p,R+1,d-p,C),t.fillRect(p,R+P-C+1,d-p,C))}}else t.fillStyle=y,t.fillRect(p,h+1,d-p,P),u&&S&&("+"===u?t.fillStyle=t.canvas.manager.get_pattern("right_strand_inv"):"-"===u&&(t.fillStyle=t.canvas.manager.get_pattern("left_strand_inv")),t.fillRect(p,h+1,d-p,P));t.globalAlpha=1,c&&"Pack"===e&&_>r&&(t.fillStyle=label_color,0===r&&p-t.measureText(c).width<0?(t.textAlign="left",t.fillText(c,d+2,h+8,this.max_label_length),v+=t.measureText(c).width+2):(t.textAlign="right",t.fillText(c,p-2,h+8,this.max_label_length),g-=t.measureText(c).width+2))}return t.globalAlpha=1,[g,v]}});var c=function(t,e,a,i,r,l,n,s,o){_.call(this,t,e,a,i,r,l,n),this.ref_seq=s?s.data:null,this.base_color_fn=o};t.extend(c.prototype,_.prototype,{get_row_height:function(){var t,e=this.mode;return"Dense"===e?t=10:"Squish"===e?t=5:(t=10,this.prefs.show_insertions&&(t*=2)),t},_parse_cigar:function(e){var a="MIDNSHP=X",i=[[0,0]],r=i[0],l=0,n=t.map(e.match(/[0-9]+[MIDNSHP=X]/g),function(t){var e=parseInt(t.slice(0,-1),10),n=t.slice(-1);return"N"===n?0!==r[1]&&(r=[l+e,l+e],i.push(r)):-1==="ISHP".indexOf(n)&&(r[1]+=e,l+=e),[a.indexOf(n),e]});return{blocks:i,cigar:n}},draw_read:function(t,i,l,n,s,o,h,_,f,c){var u=function(t){return Math.floor(Math.max(0,(t-s-.5)*l))};t.textAlign="center";var p,d,g=[s,o],v=0,w=0,y=Math.round(l/2),x=t.canvas.manager.char_width_px,M="+"===f?this.prefs.detail_block_color:this.prefs.reverse_strand_color,b="Pack"===i,S=b?9:3,k=n+1,P=new m(t,S,l,i),R=[],A=[],F=this._parse_cigar(_);_=F.cigar,R=F.blocks;for(var T=0;T<R.length;T++){var I=R[T];a([h+I[0],h+I[1]],g)&&(p=u(h+I[0]),d=u(h+I[1]),p===d&&(d+=1),t.fillStyle=M,t.fillRect(p,k,d-p,S))}for(var q=0,D=_.length;q<D;q++){var H=_[q],X="MIDNSHP=X"[H[0]],L=H[1],N=h+v;if(p=u(N),d=u(N+L),a([N,N+L],g))switch(p===d&&(d+=1),X){case"H":case"S":case"P":break;case"M":v+=L;break;case"=":case"X":var O="";"X"===X?O=c.slice(w,w+L):this.ref_seq&&(O=this.ref_seq.slice(Math.max(0,N-s),Math.min(N-s+L,o-s)));for(var j=Math.max(N,s),C=0;C<O.length;C++)if(O&&!this.prefs.show_differences||"X"===X){var B=Math.floor(Math.max(0,(j+C-s)*l));t.fillStyle=this.base_color_fn(O[C]),b&&l>x?t.fillText(O[C],B,n+9):l>.05&&t.fillRect(B-y,k,Math.max(1,Math.round(l)),S)}"X"===X&&(w+=L),v+=L;break;case"N":t.fillStyle="#ccc",t.fillRect(p,k+(S-1)/2,d-p,1),v+=L;break;case"D":P.draw_deletion(p,k,L),v+=L;break;case"I":var E=p-y;if(a([N,N+L],g)){var G=c.slice(w,w+L);if(this.prefs.show_insertions){var V=p-(d-p)/2;if(("Pack"===i||"Auto"===this.mode)&&void 0!==c&&l>x){switch(t.fillStyle="yellow",t.fillRect(V-y,n-9,d-p,9),A[A.length]={type:"triangle",data:[E,n+4,5]},t.fillStyle="#ccc",e([N,N+L],g)){case 1003:G=G.slice(s-N);break;case 1004:G=G.slice(0,N-o);break;case 1005:break;case 1002:G=G.slice(s-N,N-o)}for(var C=0,z=G.length;C<z;C++){var B=Math.floor(Math.max(0,(N+C-s)*l));t.fillText(G[C],B-(d-p)/2,n)}}else t.fillStyle="yellow",t.fillRect(V,n+("Dense"!==this.mode?2:5),d-p,"Dense"!==i?3:9)}else("Pack"===i||"Auto"===this.mode)&&void 0!==c&&l>x&&A.push({type:"text",data:[G.length,E,n+9]})}w+=L}else v=function(t,e,a){return-1!=="M=NXD".indexOf(e)&&(t+=a),t}(v,X,L),w=function(t,e,a){return-1!=="IX".indexOf(e)&&(t+=a),t}(w,X,L)}t.fillStyle="yellow";for(var J,K,Q,T=0;T<A.length;T++)J=A[T],K=J.type,Q=J.data,"text"===K?(t.save(),t.font="bold "+t.font,t.fillText(Q[0],Q[1],Q[2]),t.restore()):"triangle"===K&&r(t,Q[0],Q[1],Q[2])},draw_element:function(t,e,a,r,l,n,s,o,h){var _=(a[0],a[1]),f=a[2],c=a[3],u=Math.floor(Math.max(-.5*s,(_-l-.5)*s)),p=Math.ceil(Math.min(h,Math.max(0,(f-l-.5)*s))),d=("Dense"===e?0:0+r)*o,g="Pack"===e?9:3;this.prefs.label_color;if(a[5]instanceof Array){var v=!0;a[4][1]>=l&&a[4][0]<=n&&a[4][2]?this.draw_read(t,e,s,d,l,n,a[4][0],a[4][2],a[4][3],a[4][4]):v=!1,a[5][1]>=l&&a[5][0]<=n&&a[5][2]?this.draw_read(t,e,s,d,l,n,a[5][0],a[5][2],a[5][3],a[5][4]):v=!1;var m=Math.ceil(Math.min(h,Math.max(-.5*s,(a[4][1]-l-.5)*s))),w=Math.floor(Math.max(-.5*s,(a[5][0]-l-.5)*s));if(v&&w>m){t.fillStyle="#ccc";var y=d+1+(g-1)/2;i(t,m,y,w,y)}}else this.draw_read(t,e,s,d,l,n,_,a[4],a[5],a[6]);return"Pack"===e&&_>=l&&"."!==c&&(t.fillStyle=this.prefs.label_color,0===l&&u-t.measureText(c).width<0?(t.textAlign="left",t.fillText(c,p+2,d+9,this.max_label_length)):(t.textAlign="right",t.fillText(c,u-2,d+9,this.max_label_length))),[0,0]}});var u=function(t,e,a,i,r,l,n){f.call(this,t,e,a,i,r,l,n),this.longest_feature_length=this.calculate_longest_feature_length(),this.draw_background_connector=!1,this.draw_individual_connectors=!0};t.extend(u.prototype,_.prototype,f.prototype,{calculate_longest_feature_length:function(){for(var t=0,e=0,a=this.data.length;e<a;e++){var i=this.data[e],r=i[1],l=i[2];t=Math.max(t,l-r)}return t},get_top_padding:function(t){var e=this.view_end-this.view_start,a=t/e;return Math.min(128,Math.ceil(this.longest_feature_length/2*a))},draw_connector:function(t,e,a,i,r,l){var n=(a+i)/2,s=i-n;Math.PI;s>0&&(t.beginPath(),t.arc(n,l,i-n,Math.PI,0),t.stroke())}});var p=function(t,e){Array.isArray(t)?this.rgb=t:6==t.length?this.rgb=t.match(/.{2}/g).map(function(t){return parseInt(t,16)}):7==t.length?this.rgb=t.substring(1,7).match(/.{2}/g).map(function(t){return parseInt(t,16)}):this.rgb=t.split("").map(function(t){return parseInt(t+t,16)}),this.alpha="number"==typeof e?e:1};p.prototype={eval:function(){return this},toCSS:function(){return this.alpha<1?"rgba("+this.rgb.map(function(t){return Math.round(t)}).concat(this.alpha).join(", ")+")":"#"+this.rgb.map(function(t){return t=Math.round(t),t=(t>255?255:t<0?0:t).toString(16),1===t.length?"0"+t:t}).join("")},toHSL:function(){var t,e,a=this.rgb[0]/255,i=this.rgb[1]/255,r=this.rgb[2]/255,l=this.alpha,n=Math.max(a,i,r),s=Math.min(a,i,r),o=(n+s)/2,h=n-s;if(n===s)t=e=0;else{switch(e=o>.5?h/(2-n-s):h/(n+s),n){case a:t=(i-r)/h+(i<r?6:0);break;case i:t=(r-a)/h+2;break;case r:t=(a-i)/h+4}t/=6}return{h:360*t,s:e,l:o,a:l}},toARGB:function(){return"#"+[Math.round(255*this.alpha)].concat(this.rgb).map(function(t){return t=Math.round(t),t=(t>255?255:t<0?0:t).toString(16),1===t.length?"0"+t:t}).join("")},mix:function(t,e){color1=this;var a=e,i=2*a-1,r=color1.toHSL().a-t.toHSL().a,l=((i*r==-1?i:(i+r)/(1+i*r))+1)/2,n=1-l,s=[color1.rgb[0]*l+t.rgb[0]*n,color1.rgb[1]*l+t.rgb[1]*n,color1.rgb[2]*l+t.rgb[2]*n],o=color1.alpha*a+t.alpha*(1-a);return new p(s,o)}};var d=function(t,e,a,i){this.start_color=new p(t),this.end_color=new p(e),this.start_value=a,this.end_value=i,this.value_range=i-a};d.prototype.map_value=function(t){return t=Math.max(t,this.start_value),t=Math.min(t,this.end_value),t=(t-this.start_value)/this.value_range,this.start_color.mix(this.end_color,1-t).toCSS()};var g=function(t,e,a,i,r){this.positive_ramp=new d(e,a,0,r),this.negative_ramp=new d(e,t,0,-i),this.start_value=i,this.end_value=r};g.prototype.map_value=function(t){return t=Math.max(t,this.start_value),t=Math.min(t,this.end_value),t>=0?this.positive_ramp.map_value(t):this.negative_ramp.map_value(-t)};var v=function(t,e,a,i,r){s.call(this,t,e,a,i,r);var l,n;if(void 0===this.prefs.min_value){var o=1/0;for(l=0,n=this.data.length;l<n;l++)o=Math.min(o,this.data[l][6]);this.prefs.min_value=o}if(void 0===this.prefs.max_value){var h=-1/0;for(l=0,n=this.data.length;l<n;l++)h=Math.max(h,this.data[l][6]);this.prefs.max_value=h}};v.prototype.default_prefs={min_value:void 0,max_value:void 0,mode:"Heatmap",pos_color:"#FF8C00",neg_color:"#4169E1"},v.prototype.draw=function(t,e,a,i){var r,l,n,s,o,h,_=this.prefs.min_value,f=this.prefs.max_value,c=this.view_start,u=(this.mode,this.data),p=1/Math.sqrt(2),d=new g(this.prefs.neg_color,"#FFFFFF",this.prefs.pos_color,_,f),v=function(t){return(t-c)*i};t.save(),t.rotate(-45*Math.PI/180),t.scale(p,p);for(var m=0,w=u.length;m<w;m++)r=u[m],l=v(r[1]),n=v(r[2]),s=v(r[4]),o=v(r[5]),h=r[6],t.fillStyle=d.map_value(h),t.fillRect(l,s,n-l,o-s);t.restore()};var m=function(t,e,a,i){this.ctx=t,this.row_height=e,this.px_per_base=a,this.draw_details=("Pack"===i||"Auto"===i)&&a>=t.canvas.manager.char_width_px,this.delete_details_thickness=.2};t.extend(m.prototype,{draw_deletion:function(t,e,a){this.ctx.fillStyle="black";var i=(this.draw_details?this.delete_details_thickness:1)*this.row_height;e+=.5*(this.row_height-i),this.ctx.fillRect(t,e,a*this.px_per_base,i)}});var w=function(t,e,a,i,r,l){s.call(this,t,e,a,i,r),this.base_color_fn=l,this.divider_height=1};return t.extend(w.prototype,s.prototype,{get_row_height:function(){var t=this.mode;return"Dense"===t?10:"Squish"===t?5:10},get_required_height:function(t){var e=this.prefs.summary_height;return t>1&&this.prefs.show_sample_data&&(e+=this.divider_height+t*this.get_row_height()),e},draw:function(e,a,i,r){e.save();var l,n,s,o,h,_,f,c,u,p,d,g=function(t,e){var a=t.length,i=e.length,r=0,l=1,n=null;return"-"===e?(n="deletion",l=t.length):0===t.indexOf(e)&&a>i?(n="deletion",l=a-i,r=i):0===e.indexOf(t)&&a<i&&(n="insertion",l=i-a,r=i),null!==n?{type:n,start:r,len:l}:{}},v=Math.max(1,Math.floor(r)),w=this.data.length?this.data[0][7].split(",").length:0,y="Squish"===this.mode?5:10,x=r<.1?y:"Squish"===this.mode?3:9,M=!0,b=new m(e,y,r,this.mode);1===w&&(y=x=r<e.canvas.manager.char_width_px?this.prefs.summary_height:y,b.row_height=y,M=!1),this.prefs.show_sample_data&&M&&(e.fillStyle="#F3F3F3",e.globalAlpha=1,e.fillRect(0,this.prefs.summary_height-this.divider_height,a,this.divider_height)),e.textAlign="center";for(var S=0;S<this.data.length;S++)if(l=this.data[S],n=l[1],s=l[3],o=[l[4].split(",")],h=l[7].split(","),_=l.slice(8),o=t.map(t.flatten(o),function(e){var a={type:"snp",value:e,start:0},i=g(s,e);return t.extend(a,i)}),!(n<this.view_start||n>this.view_end)){if(M)for(e.fillStyle="#999999",e.globalAlpha=1,d=0;d<o.length;d++)for(c=this.get_start_draw_pos(n+o[d].start,r),e.fillRect(c,0,v,this.prefs.summary_height),u=this.prefs.summary_height,d=0;d<o.length;d++)e.fillStyle="deletion"===o[d].type?"black":this.base_color_fn(o[d].value),allele_frac=_/h.length,draw_height=Math.ceil(this.prefs.summary_height*allele_frac),e.fillRect(c,u-draw_height,v,draw_height),u-=draw_height;if(this.prefs.show_sample_data)for(u=M?this.prefs.summary_height+this.divider_height:0,d=0;d<h.length;d++,u+=y)if(p=h[d]?h[d].split(/\/|\|/):["0","0"],f=null,p[0]===p[1]?"."===p[0]||"0"!==p[0]&&(f=o[parseInt(p[0],10)-1],e.globalAlpha=1):(f="0"!==p[0]?p[0]:p[1],f=o[parseInt(f,10)-1],e.globalAlpha=.5),f)if(c=this.get_start_draw_pos(n+f.start,r),"snp"===f.type){var k=f.value;e.fillStyle=this.base_color_fn(k),b.draw_details?e.fillText(k,this.get_draw_pos(n,r),u+y):e.fillRect(c,u+1,v,x)}else"deletion"===f.type&&b.draw_deletion(c,u+1,f.len)}e.restore()}}),{Scaler:l,LinePainter:o,LinkedFeaturePainter:f,ReadPainter:c,ArcLinkedFeaturePainter:u,DiagonalHeatmapPainter:v,VariantPainter:w}});
//# sourceMappingURL=../../../maps/viz/trackster/painters.js.map
