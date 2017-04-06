define([],function(){function e(e){var t=this;return t.deferred=jQuery.Deferred(),t.queue=[],t.responses=[],t.numToProcess=0,t.running=!1,t.init(e||[]),t.start(),t}function t(t){var r=this;return r.names={},e.call(this,t),r}return e.prototype.init=function(e){var t=this;e.forEach(function(e){t.add(e)})},e.prototype.add=function(e){var t=this,r=this.queue.length;return this.numToProcess+=1,this.queue.push(function(){var n=r,o=e();o.done(function(e){t.deferred.notify({curr:n,total:t.numToProcess,response:e})}),o.always(function(e){t.responses.push(e),t.queue.length?t.queue.shift()():t.stop()})}),this},e.prototype.start=function(){return this.queue.length&&(this.running=!0,this.queue.shift()()),this},e.prototype.stop=function(e,t){return this.running=!1,this.queue=[],e?this.deferred.reject(t):this.deferred.resolve(this.responses),this.numToProcess=0,this.deferred=jQuery.Deferred(),this},e.prototype.done=function(e){return this.deferred.done(e)},e.prototype.fail=function(e){return this.deferred.fail(e)},e.prototype.always=function(e){return this.deferred.always(e)},e.prototype.progress=function(e){return this.deferred.progress(e)},e.create=function(t){return new e(t).deferred},t.prototype=new e,t.prototype.constructor=t,t.prototype.add=function(t){if(!t.hasOwnProperty("name")||!t.hasOwnProperty("fn"))throw new Error('NamedAjaxQueue.add requires an object with both "name" and "fn": '+JSON.stringify(t));if(!this.names.hasOwnProperty(t.name))return this.names[t.name]=!0,e.prototype.add.call(this,t.fn)},t.prototype.clear=function(){return this.names={},this},t.create=function(e){return new t(e).deferred},{AjaxQueue:e,NamedAjaxQueue:t}});
//# sourceMappingURL=../../maps/utils/ajax-queue.js.map
