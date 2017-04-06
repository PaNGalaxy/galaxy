define([],function(){var t=Backbone.Model.extend({defaults:{title:"",icon_class:"",on_click:null,menu_options:null,is_menu_button:!0,id:null,href:null,target:null,enabled:!0,visible:!0,tooltip_config:{}}}),e=Backbone.View.extend({initialize:function(){this.model.attributes.tooltip_config={placement:"bottom"},this.model.bind("change",this.render,this)},render:function(){this.$el.tooltip("hide");var t=this.template(this.model.toJSON());return t.tooltip(this.model.get("tooltip_config")),this.$el.replaceWith(t),this.setElement(t),this},events:{click:"click"},click:function(t){return!_.isFunction(this.model.get("on_click"))||(this.model.get("on_click")(t),!1)},template:function(t){var e='title="'+t.title+'" class="icon-button';return t.is_menu_button&&(e+=" menu-button"),e+=" "+t.icon_class,t.enabled||(e+="_disabled"),e+='"',t.id&&(e+=' id="'+t.id+'"'),e+=' href="'+t.href+'"',t.target&&(e+=' target="'+t.target+'"'),t.visible||(e+=' style="display: none;"'),e=t.enabled?"<a "+e+"/>":"<span "+e+"/>",$(e)}}),n=Backbone.Collection.extend({model:t}),i=Backbone.View.extend({tagName:"div",initialize:function(){this.render()},render:function(){var t=this;return this.collection.each(function(e){var n=$("<a/>").attr("href","javascript:void(0)").attr("title",e.attributes.title).addClass("icon-button menu-button").addClass(e.attributes.icon_class).appendTo(t.$el).click(e.attributes.on_click);e.attributes.tooltip_config&&n.tooltip(e.attributes.tooltip_config);var i=e.get("options");i&&make_popupmenu(n,i)}),this}});return{IconButton:t,IconButtonView:e,IconButtonCollection:n,IconButtonMenuView:i,create_icon_buttons_menu:function(e,o){o||(o={});var l=new n(_.map(e,function(e){return new t(_.extend(e,o))}));return new i({collection:l})}}});
//# sourceMappingURL=../../../maps/mvc/ui/icon-button.js.map
