<template>
    <div class="text-center">
        <h1 class="slide-header">
            {{ header }}
        </h1>
        <hr />
        <b-carousel
            indicators
            controls
            :interval="0"
            class="new-user-welcome-slides"
            no-animation
            align="center"
            position="float">
            <b-carousel-slide v-for="(slide, idx) in slides" :key="idx">
                <h2 class="carousel-caption h-md">
                    {{ slide.text | localize }}
                </h2>
                <img class="carousel-fig" :src="imgUrl(slide.file)" :class="slide.size" :alt="slide.alt" />
            </b-carousel-slide>
            <b-carousel-slide>
                <h2 class="h-md">{{ "Enjoy using Galaxy!" | localize }}</h2>
                <img class="large-img" :src="imgUrl('sections/galaxy_logo.png')" alt="Galaxy logo" />
            </b-carousel-slide>
        </b-carousel>
        <div class="button-housing">
            <b-button class="mt-auto carousel-button new-user-welcome-return" variant="primary" @click="$emit('back')"
                >Return</b-button
            >
        </div>
    </div>
</template>
<script>
import { getAppRoot } from "onload/loadConfig";

export default {
    props: {
        header: { type: String, required: true },
        slides: { type: Array, required: true },
        imageLoc: { type: String, required: false, default: "plugins/welcome_page/new_user/dist/static/topics/" },
    },
    methods: {
        imgUrl(src) {
            const root = getAppRoot();
            const url = `${root}static/${this.imageLoc}${src}`.replace("//", "/");
            return url;
        },
    },
};
</script>
