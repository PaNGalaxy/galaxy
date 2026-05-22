<script setup lang="ts">
/* global __buildTimestamp__, __license__  */
/* (injected by webpack) */

import { computed } from "vue";
import { RouterLink } from "vue-router";

import { useConfig } from "@/composables/config";
import { getAppRoot } from "@/onload/loadConfig";

import Heading from "@/components/Common/Heading.vue";
import ExternalLink from "@/components/ExternalLink.vue";
import License from "@/components/License/License.vue";
import UtcDate from "@/components/UtcDate.vue";

const { config, isConfigLoaded } = useConfig();

const clientBuildDate = __buildTimestamp__ || new Date().toISOString();
const apiDocsLink = `${getAppRoot()}api/docs`;
const galaxyLicense = __license__;

const versionUserDocumentationUrl = computed(() => {
    const configVal = config.value;
    return config.value.version_minor.slice(0, 3) === "dev"
        ? "https://docs.galaxyproject.org/en/latest/releases/index.html"
        : `${configVal.release_doc_base_url}${configVal.version_major}/releases/${configVal.version_major}_announce_user.html`;
});
</script>

<template>
    <div v-if="isConfigLoaded" class="about-galaxy">
        <div class="p-2">
            <Heading h2 separator size="md">Support</Heading>
            <p>
                If you need support, then you can directly open a ticket in the
                <ExternalLink :href="config.dashboard_url">
                    <strong v-localize>NOVA Dashboard</strong>
                </ExternalLink>,
                or you can email
                <ExternalLink :href="`mailto:${config.support_url}`">
                    <strong v-localize>{{ config.support_url }}</strong>
                </ExternalLink>.
            </p>
            <Heading h2 separator size="md">About NDIP and Galaxy</Heading>
            <div>
                <!-- Galaxy version (detailed), with a link to the release notes -->
                <ExternalLink :href="versionUserDocumentationUrl">
                    <strong v-localize>Release Notes</strong>
                </ExternalLink>
                <p v-localize>
                    This Galaxy server version is <strong>{{ config.version_major }}.{{ config.version_minor }}</strong
                    >, and the web client was built on
                    <strong><UtcDate :date="clientBuildDate" mode="pretty" /></strong>.
                </p>
                <template v-if="config.version_extra">
                    <p v-localize>The server also provides the following extra version information</p>
                    <ul>
                        <li v-for="([name, value], index) in Object.entries(config.version_extra)" :key="index">
                            <strong>{{ name }}</strong>
                            : {{ value }}
                        </li>
                    </ul>
                </template>
            </div>
            <div>
                <ExternalLink href="https://link.springer.com/chapter/10.1007/978-3-031-23606-8_9">
                    <strong v-localize>How to Cite NDIP</strong>
                </ExternalLink>
                <p v-localize>
                    If you find NDIP useful, please cite our SMC 2022 paper which also gives a high-level overview to
                    the motivation and goals of the Neutrons Data Interpretation Platform.
                </p>
            </div>
            <div v-if="config.citation_url">
                <ExternalLink :href="config.citation_url">
                    <strong v-localize>How to Cite Galaxy</strong>
                </ExternalLink>
                <p v-localize>View details on how to properly cite Galaxy.</p>
            </div>
            <div>
                <License class="font-weight-bold" :license-id="galaxyLicense" />
                <p v-localize>The Galaxy Software is licensed under the MIT License.</p>
            </div>
            <div v-if="config.terms_url">
                <!-- Terms, if available.-->
                <ExternalLink :href="config.terms_url">
                    <strong v-localize>Terms and Conditions</strong>
                </ExternalLink>
                <p v-localize>
                    This Galaxy Server has specified Terms and Conditions that apply to use of the service.
                </p>
            </div>
            <Heading h2 separator size="md">Documentation</Heading>
            <div>
                <ExternalLink href="/docs/">
                    <strong v-localize>NDIP Documentation</strong>
                </ExternalLink>
            </div>
            <div>
                <ExternalLink :href="apiDocsLink">
                    <strong v-localize>Galaxy API Documentation</strong>
                </ExternalLink>
                <p v-localize>Explore the Galaxy API.</p>
            </div>
            <div>
                <RouterLink to="tours">
                    <strong v-localize>Interactive Tours</strong>
                </RouterLink>
                <p v-localize>Discover and learn about Galaxy with our interactive tours.</p>
            </div>
            <div v-if="config.screencasts_url">
                <ExternalLink :href="config.screencasts_url">
                    <strong v-localize>Videos and Screencasts</strong>
                </ExternalLink>
                <p v-localize>Learn more about Galaxy by watching videos and screencasts.</p>
            </div>
            <Heading h2 separator size="md">Acknowledgement Statement</Heading>
            <div>
                This work was sponsored by the Laboratory Directed Research and Development Program of Oak
                Ridge National Laboratory, managed by UT-Battelle, LLC, for the U.S. Department of Energy.
            </div>
        </div>
    </div>
</template>

<style lang="scss" scoped>
@import "theme/blue.scss";

.about-galaxy h1 {
    --fa-primary-color: #{$brand-primary};
    --fa-secondary-color: #{$brand-toggle};
    --fa-secondary-opacity: 1;
}
</style>
