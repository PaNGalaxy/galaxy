<template>
    <tr>
        <td>
            {{ codeLabel }}
        </td>
        <td v-if="codeItem">
            <b-row align-v="center">
                <b-col cols="11">
                    <pre :class="codeClass">{{ codeItem }}</pre>
                </b-col>
                <b-col class="nopadding pointer"
                    v-b-tooltip.hover
                    :title="`click to ${action}`"
                    @mouseup="toggleExpanded()">
                    <font-awesome-icon :icon="iconClass" />
                </b-col>
            </b-row>
        </td>
        <td v-else><i>empty</i></td>
    </tr>
</template>
<script>
import { faCompressAlt, faExpandAlt } from "@fortawesome/free-solid-svg-icons";
import { library } from "@fortawesome/fontawesome-svg-core";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";

library.add(faCompressAlt, faExpandAlt);
export default {
    components: {
        FontAwesomeIcon,
    },
    props: {
        codeLabel: String,
        codeItem: String,
    },
    data() {
        return {
            expanded: false,
            lastPos: 0,
        };
    },
    computed: {
        action() {
            return this.expanded ? "collapse" : "expand";
        },
        codeClass() {
            return this.expanded ? "code" : "code preview";
        },
        iconClass() {
            return this.expanded ? ["fas", "compress-alt"] : ["fas", "expand-alt"];
        },
    },
    updated() {
        try {
            var codeDiv = this.$el.querySelector(".code");
            if (codeDiv.scrollTop + codeDiv.offsetHeight >= this.lastPos - 5)  {
                    // scroll is at the bottom
                    codeDiv.scrollTop = codeDiv.scrollHeight;
            }
            this.lastPos = codeDiv.scrollHeight;
        } catch(exception) {
            console.debug("Code div is not present");
        }
    },
    methods: {
        toggleExpanded() {
            if (this.codeItem) {
                this.expanded = !this.expanded;
            }
        },
    },
};
</script>

<style scoped>
.pointer {
    cursor: pointer;
}

.code {
    max-height: 50em;
    overflow: auto;
}

.nopadding {
    padding: 0;
    margin: 0;
}
</style>
