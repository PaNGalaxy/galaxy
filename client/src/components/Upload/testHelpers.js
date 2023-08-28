import _ from "underscore";
import Backbone from "backbone";
import "utils/uploadbox";
import { mount, createLocalVue } from "@vue/test-utils";
import BootstrapVue from "bootstrap-vue";

export const createMockDetails = (options = {}) => {
    return _.defaults(options, {
        defaultExtension: "auto",
        currentFtp: "ftp://localhost",
        model: new Backbone.Model(),
        effectiveExtensions: [
            { id: "ab1", text: "ab1", description: "A binary sequence file in 'ab1' format with a '.ab1'" },
            {
                id: "affybatch",
                text: "affybatch",
                description: null,
                composite_files: [
                    {
                        name: "%s.pheno",
                        optional: false,
                        description: "Phenodata tab text file",
                    },
                    {
                        name: "%s.affybatch",
                        optional: false,
                        description: "AffyBatch R object saved to file",
                    },
                ],
            },
        ],
    });
};

export function mountWithDetails(component, options = {}, propsData_ = {}) {
    const details = createMockDetails(options);
    const propsData = _.defaults(propsData_, { details });

    const localVue = createLocalVue();
    localVue.use(BootstrapVue);

    const wrapper = mount(component, {
        propsData,
        localVue,
        attachTo: document.body,
        stubs: {
            select2: true,
        },
    });

    return { wrapper, localVue };
}
