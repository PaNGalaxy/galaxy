!function(e){jQuery.event.props.push("dataTransfer"),e.uploadpost=function(r){var n=e.extend({},{data:{},success:function(){},error:function(){},progress:function(){},url:null,maxfilesize:2048,error_filesize:"File exceeds 2GB. Please use a FTP client.",error_default:"Please make sure the file is available.",error_server:"Upload request failed.",error_login:"Uploads require you to log in."},r),t=n.data;if(t.error_message)return void n.error(t.error_message);var o=new FormData;for(var a in t.payload)o.append(a,t.payload[a]);var i=0;for(var a in t.files){var u=t.files[a];o.append(u.name,u.file,u.file.name),i+=u.file.size}if(i>1048576*n.maxfilesize)return void n.error(n.error_filesize);xhr=new XMLHttpRequest,xhr.open("POST",n.url,!0),xhr.setRequestHeader("Accept","application/json"),xhr.setRequestHeader("Cache-Control","no-cache"),xhr.setRequestHeader("X-Requested-With","XMLHttpRequest"),xhr.onreadystatechange=function(){if(xhr.readyState==xhr.DONE){var e=null;if(xhr.responseText)try{e=jQuery.parseJSON(xhr.responseText)}catch(r){e=xhr.responseText}if(xhr.status<200||xhr.status>299){var r=xhr.statusText;403==xhr.status?r=n.error_login:0==xhr.status?r=n.error_server:r||(r=n.error_default),n.error(r+" ("+xhr.status+")")}else n.success(e)}},xhr.upload.addEventListener("progress",function(e){e.lengthComputable&&n.progress(Math.round(100*e.loaded/e.total))},!1),Galaxy.emit.debug("uploadbox::uploadpost()","Posting following data.",n),xhr.send(o)},e.fn.uploadinput=function(r){var n=this,t=e.extend({},{ondragover:function(){},ondragleave:function(){},onchange:function(){},multiple:!1},r),o=e('<input type="file" style="display: none" '+(t.multiple&&"multiple"||"")+"/>");return n.append(o.change(function(r){t.onchange(r.target.files),e(this).val("")})),n.on("drop",function(e){t.ondragleave(e),e.dataTransfer&&(t.onchange(e.dataTransfer.files),e.preventDefault())}),n.on("dragover",function(e){e.preventDefault(),t.ondragover(e)}),n.on("dragleave",function(e){e.stopPropagation(),t.ondragleave(e)}),{dialog:function(){o.trigger("click")}}},e.fn.uploadbox=function(r){function n(e){if(e&&e.length&&!h){var r=p;return _.each(e,function(e,r){"new"!==e.mode&&_.filter(d,function(r){return r.name===e.name&&r.size===e.size}).length&&(e.duplicate=!0)}),_.each(e,function(e){if(!e.duplicate){var r=String(p++);d[r]=e,f.announce(r,d[r]),g++}}),r}}function t(e){d[e]&&(delete d[e],g--)}function o(){if(0==g||v)return v=!1,h=!1,void f.complete();h=!0;var r=-1;for(var n in d){r=n;break}d[r];t(r),e.uploadpost({url:f.url,data:f.initialize(r),success:function(e){f.success(r,e),o()},error:function(e){f.error(r,e),o()},progress:function(e){f.progress(r,e)}})}function a(){x.dialog()}function i(e){for(e in d)t(e)}function u(){h||(h=!0,o())}function s(){v=!0}function l(r){return f=e.extend({},f,r)}function c(){return window.File&&window.FormData&&window.XMLHttpRequest&&window.FileList}var f=e.extend({},{dragover:function(){},dragleave:function(){},announce:function(e){},initialize:function(e){},progress:function(e,r){},success:function(e,r){},error:function(e,r){alert(r)},complete:function(){}},r),d={},p=0,g=0,h=!1,v=!1,x=e(this).uploadinput({multiple:!0,onchange:function(e){n(e)},ondragover:r.ondragover,ondragleave:r.ondragleave});return{select:a,add:n,remove:t,start:u,stop:s,reset:i,configure:l,compatible:c}}}(jQuery);
//# sourceMappingURL=../../maps/utils/uploadbox.js.map
