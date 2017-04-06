!function(t,e){var o,n;n=e.document,o=function(){function o(o){var n;try{n=e.localStorage}catch(t){n=!1}this._options=t.extend({name:"tour",steps:[],container:"body",autoscroll:!0,keyboard:!0,storage:n,debug:!1,backdrop:!1,backdropContainer:"body",backdropPadding:0,redirect:!0,orphan:!1,duration:!1,delay:!1,basePath:"",template:'<div class="popover" role="tooltip"> <div class="arrow"></div> <h3 class="popover-title"></h3> <div class="popover-content"></div> <div class="popover-navigation"> <div class="btn-group"> <button class="btn btn-sm btn-default" data-role="prev">&laquo; Prev</button> <button class="btn btn-sm btn-default" data-role="next">Next &raquo;</button> <button class="btn btn-sm btn-default" data-role="pause-resume" data-pause-text="Pause" data-resume-text="Resume">Pause</button> </div> <button class="btn btn-sm btn-default" data-role="end">End tour</button> </div> </div>',afterSetState:function(t,e){},afterGetState:function(t,e){},afterRemoveState:function(t){},onStart:function(t){},onEnd:function(t){},onShow:function(t){},onShown:function(t){},onHide:function(t){},onHidden:function(t){},onNext:function(t){},onPrev:function(t){},onPause:function(t,e){},onResume:function(t,e){},onRedirectError:function(t){}},o),this._force=!1,this._inited=!1,this._current=null,this.backdrop={overlay:null,$element:null,$background:null,backgroundShown:!1,overlayElementShown:!1}}return o.prototype.addSteps=function(t){var e,o,n;for(o=0,n=t.length;o<n;o++)e=t[o],this.addStep(e);return this},o.prototype.addStep=function(t){return this._options.steps.push(t),this},o.prototype.getStep=function(e){if(null!=this._options.steps[e])return t.extend({id:"step-"+e,path:"",host:"",placement:"right",title:"",content:"<p></p>",next:e===this._options.steps.length-1?-1:e+1,prev:e-1,animation:!0,container:this._options.container,autoscroll:this._options.autoscroll,backdrop:this._options.backdrop,backdropContainer:this._options.backdropContainer,backdropPadding:this._options.backdropPadding,redirect:this._options.redirect,reflexElement:this._options.steps[e].element,orphan:this._options.orphan,duration:this._options.duration,delay:this._options.delay,template:this._options.template,onShow:this._options.onShow,onShown:this._options.onShown,onHide:this._options.onHide,onHidden:this._options.onHidden,onNext:this._options.onNext,onPrev:this._options.onPrev,onPause:this._options.onPause,onResume:this._options.onResume,onRedirectError:this._options.onRedirectError},this._options.steps[e])},o.prototype.init=function(t){return this._force=t,this.ended()?(this._debug("Tour ended, init prevented."),this):(this.setCurrentStep(),this._initMouseNavigation(),this._initKeyboardNavigation(),this._onResize(function(t){return function(){return t.showStep(t._current)}}(this)),null!==this._current&&this.showStep(this._current),this._inited=!0,this)},o.prototype.start=function(t){var e;return null==t&&(t=!1),this._inited||this.init(t),null===this._current&&(e=this._makePromise(null!=this._options.onStart?this._options.onStart(this):void 0),this._callOnPromiseDone(e,this.showStep,0)),this},o.prototype.next=function(){var t;return t=this.hideStep(this._current),this._callOnPromiseDone(t,this._showNextStep)},o.prototype.prev=function(){var t;return t=this.hideStep(this._current),this._callOnPromiseDone(t,this._showPrevStep)},o.prototype.goTo=function(t){var e;return e=this.hideStep(this._current),this._callOnPromiseDone(e,this.showStep,t)},o.prototype.end=function(){var o,r;return o=function(o){return function(r){if(t(n).off("click.tour-"+o._options.name),t(n).off("keyup.tour-"+o._options.name),t(e).off("resize.tour-"+o._options.name),o._setState("end","yes"),o._inited=!1,o._force=!1,o._clearTimer(),null!=o._options.onEnd)return o._options.onEnd(o)}}(this),r=this.hideStep(this._current),this._callOnPromiseDone(r,o)},o.prototype.ended=function(){return!this._force&&!!this._getState("end")},o.prototype.restart=function(){return this._removeState("current_step"),this._removeState("end"),this._removeState("redirect_to"),this.start()},o.prototype.pause=function(){var t;return(t=this.getStep(this._current))&&t.duration?(this._paused=!0,this._duration-=(new Date).getTime()-this._start,e.clearTimeout(this._timer),this._debug("Paused/Stopped step "+(this._current+1)+" timer ("+this._duration+" remaining)."),null!=t.onPause?t.onPause(this,this._duration):void 0):this},o.prototype.resume=function(){var t;return(t=this.getStep(this._current))&&t.duration?(this._paused=!1,this._start=(new Date).getTime(),this._duration=this._duration||t.duration,this._timer=e.setTimeout(function(t){return function(){return t._isLast()?t.next():t.end()}}(this),this._duration),this._debug("Started step "+(this._current+1)+" timer with duration "+this._duration),null!=t.onResume&&this._duration!==t.duration?t.onResume(this,this._duration):void 0):this},o.prototype.hideStep=function(e){var o,n,r;if(r=this.getStep(e))return this._clearTimer(),n=this._makePromise(null!=r.onHide?r.onHide(this,e):void 0),o=function(o){return function(n){var i;if(i=t(r.element),i.data("bs.popover")||i.data("popover")||(i=t("body")),i.popover("destroy").removeClass("tour-"+o._options.name+"-element tour-"+o._options.name+"-"+e+"-element"),i.removeData("bs.popover"),r.reflex&&t(r.reflexElement).removeClass("tour-step-element-reflex").off(o._reflexEvent(r.reflex)+".tour-"+o._options.name),r.backdrop&&o._hideBackdrop(),null!=r.onHidden)return r.onHidden(o)}}(this),this._callOnPromiseDone(n,o),n},o.prototype.showStep=function(t){var o,r,i,s;return this.ended()?(this._debug("Tour ended, showStep prevented."),this):(s=this.getStep(t))?(i=t<this._current,o=this._makePromise(null!=s.onShow?s.onShow(this,t):void 0),r=function(e){return function(o){var r,a;if(e.setCurrentStep(t),r=function(){switch({}.toString.call(s.path)){case"[object Function]":return s.path();case"[object String]":return this._options.basePath+s.path;default:return s.path}}.call(e),!e._isRedirect(s.host,r,n.location)||(e._redirect(s,t,r),e._isJustPathHashDifferent(s.host,r,n.location))){if(e._isOrphan(s)){if(!1===s.orphan)return e._debug("Skip the orphan step "+(e._current+1)+".\nOrphan option is false and the element does not exist or is hidden."),void(i?e._showPrevStep():e._showNextStep());e._debug("Show the orphan step "+(e._current+1)+". Orphans option is true.")}return s.backdrop&&e._showBackdrop(s),a=function(){if(e.getCurrentStep()===t&&!e.ended())return null!=s.element&&s.backdrop&&e._showOverlayElement(s),e._showPopover(s,t),null!=s.onShown&&s.onShown(e),e._debug("Step "+(e._current+1)+" of "+e._options.steps.length)},s.autoscroll?e._scrollIntoView(s.element,a):a(),s.duration?e.resume():void 0}}}(this),s.delay?(this._debug("Wait "+s.delay+" milliseconds to show the step "+(this._current+1)),e.setTimeout(function(t){return function(){return t._callOnPromiseDone(o,r)}}(this),s.delay)):this._callOnPromiseDone(o,r),o):void 0},o.prototype.getCurrentStep=function(){return this._current},o.prototype.setCurrentStep=function(t){return null!=t?(this._current=t,this._setState("current_step",t)):(this._current=this._getState("current_step"),this._current=null===this._current?null:parseInt(this._current,10)),this},o.prototype.redraw=function(){return this._showOverlayElement(this.getStep(this.getCurrentStep()).element,!0)},o.prototype._setState=function(t,e){var o,n;if(this._options.storage){n=this._options.name+"_"+t;try{this._options.storage.setItem(n,e)}catch(t){o=t,o.code===DOMException.QUOTA_EXCEEDED_ERR&&this._debug("LocalStorage quota exceeded. State storage failed.")}return this._options.afterSetState(n,e)}return null==this._state&&(this._state={}),this._state[t]=e},o.prototype._removeState=function(t){var e;return this._options.storage?(e=this._options.name+"_"+t,this._options.storage.removeItem(e),this._options.afterRemoveState(e)):null!=this._state?delete this._state[t]:void 0},o.prototype._getState=function(t){var e,o;return this._options.storage?(e=this._options.name+"_"+t,o=this._options.storage.getItem(e)):null!=this._state&&(o=this._state[t]),void 0!==o&&"null"!==o||(o=null),this._options.afterGetState(t,o),o},o.prototype._showNextStep=function(){var t,e,o;return o=this.getStep(this._current),e=function(t){return function(e){return t.showStep(o.next)}}(this),t=this._makePromise(null!=o.onNext?o.onNext(this):void 0),this._callOnPromiseDone(t,e)},o.prototype._showPrevStep=function(){var t,e,o;return o=this.getStep(this._current),e=function(t){return function(e){return t.showStep(o.prev)}}(this),t=this._makePromise(null!=o.onPrev?o.onPrev(this):void 0),this._callOnPromiseDone(t,e)},o.prototype._debug=function(t){if(this._options.debug)return e.console.log("Bootstrap Tour '"+this._options.name+"' | "+t)},o.prototype._isRedirect=function(t,e,o){var n;return!(""===t||!this._isHostDifferent(t,o.href))||(n=[o.pathname,o.search,o.hash].join(""),null!=e&&""!==e&&("[object RegExp]"==={}.toString.call(e)&&!e.test(n)||"[object String]"==={}.toString.call(e)&&this._isPathDifferent(e,n)))},o.prototype._isHostDifferent=function(t,e){return this._getProtocol(t)!==this._getProtocol(e)||this._getHost(t)!==this._getHost(e)},o.prototype._isPathDifferent=function(t,e){return this._getPath(t)!==this._getPath(e)||!this._equal(this._getQuery(t),this._getQuery(e))||!this._equal(this._getHash(t),this._getHash(e))},o.prototype._isJustPathHashDifferent=function(t,e,o){var n;return(""===t||!this._isHostDifferent(t,o.href))&&(n=[o.pathname,o.search,o.hash].join(""),"[object String]"==={}.toString.call(e)&&(this._getPath(e)===this._getPath(n)&&this._equal(this._getQuery(e),this._getQuery(n))&&!this._equal(this._getHash(e),this._getHash(n))))},o.prototype._redirect=function(e,o,r){if(t.isFunction(e.redirect))return e.redirect.call(this,r);if(!0===e.redirect){if(this._debug("Redirect to "+e.host+r),this._getState("redirect_to")!==""+o)return this._setState("redirect_to",""+o),n.location.href=""+e.host+r;if(this._debug("Error redirection loop to "+r),this._removeState("redirect_to"),null!=e.onRedirectError)return e.onRedirectError(this)}},o.prototype._isOrphan=function(e){return null==e.element||!t(e.element).length||t(e.element).is(":hidden")&&"http://www.w3.org/2000/svg"!==t(e.element)[0].namespaceURI},o.prototype._isLast=function(){return this._current<this._options.steps.length-1},o.prototype._showPopover=function(e,o){var n,r,i,s,a;if(t(".tour-"+this._options.name).remove(),s=t.extend({},this._options),i=this._isOrphan(e),e.template=this._template(e,o),i&&(e.element="body",e.placement="top"),n=t(e.element),n.addClass("tour-"+this._options.name+"-element tour-"+this._options.name+"-"+o+"-element"),e.options&&t.extend(s,e.options),e.reflex&&!i&&t(e.reflexElement).addClass("tour-step-element-reflex").off(this._reflexEvent(e.reflex)+".tour-"+this._options.name).on(this._reflexEvent(e.reflex)+".tour-"+this._options.name,function(t){return function(){return t._isLast()?t.next():t.end()}}(this)),a=!0===e.smartPlacement&&-1===e.placement.search(/auto/i),n.popover({placement:a?"auto "+e.placement:e.placement,trigger:"manual",title:e.title,content:e.content,html:!0,animation:e.animation,container:e.container,template:e.template,selector:e.element}).popover("show"),r=n.data("bs.popover")?n.data("bs.popover").tip():n.data("popover").tip(),r.attr("id",e.id),this._reposition(r,e),i)return this._center(r)},o.prototype._template=function(e,o){var n,r,i,s,a,p;return p=e.template,this._isOrphan(e)&&"[object Boolean]"!=={}.toString.call(e.orphan)&&(p=e.orphan),a=t(t.isFunction(p)?p(o,e):p),n=a.find(".popover-navigation"),i=n.find('[data-role="prev"]'),r=n.find('[data-role="next"]'),s=n.find('[data-role="pause-resume"]'),this._isOrphan(e)&&a.addClass("orphan"),a.addClass("tour-"+this._options.name+" tour-"+this._options.name+"-"+o),e.reflex&&a.addClass("tour-"+this._options.name+"-reflex"),e.prev<0&&(i.addClass("disabled"),i.prop("disabled",!0)),e.next<0&&(r.addClass("disabled"),r.prop("disabled",!0)),e.duration||s.remove(),a.clone().wrap("<div>").parent().html()},o.prototype._reflexEvent=function(t){return"[object Boolean]"==={}.toString.call(t)?"click":t},o.prototype._reposition=function(e,o){var r,i,s,a,p,u,h;if(a=e[0].offsetWidth,i=e[0].offsetHeight,h=e.offset(),p=h.left,u=h.top,r=t(n).outerHeight()-h.top-e.outerHeight(),r<0&&(h.top=h.top+r),s=t("html").outerWidth()-h.left-e.outerWidth(),s<0&&(h.left=h.left+s),h.top<0&&(h.top=0),h.left<0&&(h.left=0),e.offset(h),"bottom"===o.placement||"top"===o.placement){if(p!==h.left)return this._replaceArrow(e,2*(h.left-p),a,"left")}else if(u!==h.top)return this._replaceArrow(e,2*(h.top-u),i,"top")},o.prototype._center=function(o){return o.css("top",t(e).outerHeight()/2-o.outerHeight()/2)},o.prototype._replaceArrow=function(t,e,o,n){return t.find(".arrow").css(n,e?50*(1-e/o)+"%":"")},o.prototype._scrollIntoView=function(o,n){var r,i,s,a,p,u;return r=t(o),r.length?(i=t(e),a=r.offset().top,u=i.height(),p=Math.max(0,a-u/2),this._debug("Scroll into view. ScrollTop: "+p+". Element offset: "+a+". Window height: "+u+"."),s=0,t("body, html").stop(!0,!0).animate({scrollTop:Math.ceil(p)},function(t){return function(){if(2==++s)return n(),t._debug("Scroll into view.\nAnimation end element offset: "+r.offset().top+".\nWindow height: "+i.height()+".")}}(this))):n()},o.prototype._onResize=function(o,n){return t(e).on("resize.tour-"+this._options.name,function(){return clearTimeout(n),n=setTimeout(o,100)})},o.prototype._initMouseNavigation=function(){var e;return e=this,t(n).off("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='prev']").off("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='next']").off("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='end']").off("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='pause-resume']").on("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='next']",function(t){return function(e){return e.preventDefault(),t.next()}}(this)).on("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='prev']",function(t){return function(e){return e.preventDefault(),t.prev()}}(this)).on("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='end']",function(t){return function(e){return e.preventDefault(),t.end()}}(this)).on("click.tour-"+this._options.name,".popover.tour-"+this._options.name+" *[data-role='pause-resume']",function(o){var n;return o.preventDefault(),n=t(this),n.text(e._paused?n.data("pause-text"):n.data("resume-text")),e._paused?e.resume():e.pause()})},o.prototype._initKeyboardNavigation=function(){if(this._options.keyboard)return t(n).on("keyup.tour-"+this._options.name,function(t){return function(e){if(e.which)switch(e.which){case 39:return e.preventDefault(),t._isLast()?t.next():t.end();case 37:if(e.preventDefault(),t._current>0)return t.prev();break;case 27:return e.preventDefault(),t.end()}}}(this))},o.prototype._makePromise=function(e){return e&&t.isFunction(e.then)?e:null},o.prototype._callOnPromiseDone=function(t,e,o){return t?t.then(function(t){return function(n){return e.call(t,o)}}(this)):e.call(this,o)},o.prototype._showBackdrop=function(e){if(!this.backdrop.backgroundShown)return this.backdrop=t("<div>",{class:"tour-backdrop"}),this.backdrop.backgroundShown=!0,t(e.backdropContainer).append(this.backdrop)},o.prototype._hideBackdrop=function(){return this._hideOverlayElement(),this._hideBackground()},o.prototype._hideBackground=function(){if(this.backdrop)return this.backdrop.remove(),this.backdrop.overlay=null,this.backdrop.backgroundShown=!1},o.prototype._showOverlayElement=function(e,o){var n,r;if((n=t(e.element))&&0!==n.length&&(!this.backdrop.overlayElementShown||o))return this.backdrop.overlayElementShown||(this.backdrop.$element=n.addClass("tour-step-backdrop"),this.backdrop.$background=t("<div>",{class:"tour-step-background"}),this.backdrop.$background.appendTo(e.backdropContainer),this.backdrop.overlayElementShown=!0),r={width:n.innerWidth(),height:n.innerHeight(),offset:n.offset()},e.backdropPadding&&(r=this._applyBackdropPadding(e.backdropPadding,r)),this.backdrop.$background.width(r.width).height(r.height).offset(r.offset)},o.prototype._hideOverlayElement=function(){if(this.backdrop.overlayElementShown)return this.backdrop.$element.removeClass("tour-step-backdrop"),this.backdrop.$background.remove(),this.backdrop.$element=null,this.backdrop.$background=null,this.backdrop.overlayElementShown=!1},o.prototype._applyBackdropPadding=function(t,e){return"object"==typeof t?(null==t.top&&(t.top=0),null==t.right&&(t.right=0),null==t.bottom&&(t.bottom=0),null==t.left&&(t.left=0),e.offset.top=e.offset.top-t.top,e.offset.left=e.offset.left-t.left,e.width=e.width+t.left+t.right,e.height=e.height+t.top+t.bottom):(e.offset.top=e.offset.top-t,e.offset.left=e.offset.left-t,e.width=e.width+2*t,e.height=e.height+2*t),e},o.prototype._clearTimer=function(){return e.clearTimeout(this._timer),this._timer=null,this._duration=null},o.prototype._getProtocol=function(t){return t=t.split("://"),t.length>1?t[0]:"http"},o.prototype._getHost=function(t){return t=t.split("//"),t=t.length>1?t[1]:t[0],t.split("/")[0]},o.prototype._getPath=function(t){return t.replace(/\/?$/,"").split("?")[0].split("#")[0]},o.prototype._getQuery=function(t){return this._getParams(t,"?")},o.prototype._getHash=function(t){return this._getParams(t,"#")},o.prototype._getParams=function(t,e){var o,n,r,i,s;if(n=t.split(e),1===n.length)return{};for(n=n[1].split("&"),r={},i=0,s=n.length;i<s;i++)o=n[i],o=o.split("="),r[o[0]]=o[1]||"";return r},o.prototype._equal=function(t,e){var o,n;if("[object Object]"==={}.toString.call(t)&&"[object Object]"==={}.toString.call(e)){for(o in t)if(n=t[o],e[o]!==n)return!1;for(o in e)if(n=e[o],t[o]!==n)return!1;return!0}return t===e},o}(),e.Tour=o}(jQuery,window);
//# sourceMappingURL=../../maps/libs/bootstrap-tour.js.map
