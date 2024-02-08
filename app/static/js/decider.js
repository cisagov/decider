$(document).ready(function () {
    const needsAWelcome = localStorage.getItem('has-seen-welcome') === null;
    if (needsAWelcome) {
        const welcomeModal = new bootstrap.Modal(document.getElementById('welcomeModal'));
        welcomeModal.show();
    }
});

// broofa's UUIDv4 generator
// https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid/2117523#2117523
function uuidv4() {
    return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
        (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
}

function resolveURL(url) {
    // local -> add baseURL
    if (url.startsWith('/')) {
        return _.trimEnd(document.baseURI, '/') + url;
    }

    // external -> pass-through
    else {
        return url;
    }
}

function urlSearchParamsV2(params) {
    const paramArr = [];

    Object.entries(params).forEach(([key, val]) => {
        if (Array.isArray(val)) {
            val.forEach((valItem) => {
                paramArr.push([key, valItem]);
            });
        } else {
            paramArr.push([key, val]);
        }
    });

    const paramStr = new URLSearchParams(paramArr).toString();
    return paramStr;
}

function getURLNoHash() {
    return (
        location.protocol +
        '//' +
        location.hostname +
        (location.port ? ':' + location.port : '') +
        location.pathname +
        (location.search ? location.search : '')
    );
}

async function fetchV2(args) {
    const method = args.method ?? args.type ?? 'GET';
    let endpoint = args.endpoint ?? args.url;
    const body = args.body;
    const params = args.params;

    // params (dict) -> url search params
    if (typeof params !== 'undefined') {
        const paramStr = urlSearchParamsV2(params);
        if (paramStr.length > 0) {
            endpoint = `${endpoint}?${paramStr}`;
        }
    }

    // always request json back
    const request = {
        headers: { Accept: 'application/json' },
        method: method,
    };

    // body is json if present
    if (typeof body !== 'undefined') {
        request.headers['Content-Type'] = 'application/json';
        request.body = JSON.stringify(body);
    }

    // POST et al & not cross-domain -> add CSRF
    if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method) && endpoint.startsWith('/')) {
        request.headers['X-CSRFToken'] = csrfToken;
    }

    let response, responseText, responseJSON;

    // make request
    try {
        response = await fetch(resolveURL(endpoint), request);
        responseText = await response.text();
    } catch {
        return { netFail: true };
    }

    // process request json
    try {
        responseJSON = JSON.parse(responseText);
        return { netFail: false, ok: response.ok, data: responseJSON };
    } catch {
        return { netFail: false, ok: false, data: { message: 'got non-json response', text: responseText } };
    }
}

function doToast(text, success = true) {
    // template -> jQ obj
    const toastJQ = $($('#templateToast').html());

    // pass alpine args
    const data = JSON.stringify({ text, success });
    toastJQ.attr('x-data', `toast(${data})`);

    // bootstrap make + show
    const destination = success ? '#successToasts' : '#failureToasts';
    const toastEl = toastJQ.appendTo(destination).get(0);
    const toastBS = new bootstrap.Toast(toastEl, {
        autohide: success,
        delay: 7000,
    });
    toastBS.show();
}

function cleanupFilterObject(o, sort) {
    o.value = o.kind;
    o.name = o.title_name;
    delete o.kind;
    delete o.title_name;
    o.items = o.items.map((i) => ({ value: i.internal_name, name: i.human_name }));

    if (sort) {
        o.items.sort((a, b) => a.name.localeCompare(b.name));
    }
}

function filterQuestionHTML(html) {
    // optionally removes wrapping <p></p> present on all questions except Home
    // removes the multiple <p>s on T1069, T1070
    return html.replace(/<([^>]+)>/gi, (match, inside) => {
        if (['strong', '/strong', 'em', '/em'].includes(inside)) {
            return match;
        } else {
            return '';
        }
    });
}

function bracketizeCrumbIDs(crumbs) {
    // crumb names: 'Name (ID)' -> 'Name [ID]'
    return crumbs.map(({ url, name }) => ({ url, name: name.replaceAll('(', '[').replaceAll(')', ']') }));
}

document.addEventListener('alpine:init', function () {
    Alpine.store('attackIDHelper', {
        loadedVersion: null,

        // matrix order
        tactIDs: [],

        // id -> name resolution / existence
        tactNameLookup: {},
        techNameLookup: {},

        // relationship existence check (`tactId--techId`)
        tactTechIDPairs: new Set(),

        async load(version) {
            if (this.loadedVersion === version) {
                return;
            }

            const allVersions = Alpine.store('global').versionPicker.all_versions;
            if (!allVersions.includes(version)) {
                doToast(
                    `That version is not present on the server. Only ATT&CK Enterprise [${allVersions.join(
                        ', '
                    )}] are installed.`,
                    false
                );
                return;
            }

            const response = await fetchV2({
                url: '/api/tactics',
                params: { version: version },
            });
            if (response.netFail || !response.ok) {
                doToast('Failed to get data to help validate ATT&CK IDs. Please refresh.', false);
                return;
            }
            const tactics = response.data;

            tactics.forEach((tact) => {
                const tactId = tact.tactic_id;
                const tactName = tact.tactic_name;

                this.tactIDs.push(tactId);
                this.tactNameLookup[tactId] = tactName;

                tact.techniques.forEach((tech) => {
                    const techId = tech.technique_id;
                    const techName = tech.technique_name;

                    this.techNameLookup[techId] = techName;
                    this.tactTechIDPairs.add(`${tactId}--${techId}`);
                });
            });

            this.loadedVersion = version;
        },

        doesTactTechPairExist(tactId, techId) {
            return this.tactTechIDPairs.has(`${tactId}--${techId}`);
        },

        getTechFullName(techId) {
            // sub
            if (techId.includes('.')) {
                const baseId = techId.split('.')[0];

                return `${this.techNameLookup[baseId]}: ${this.techNameLookup[techId]}`;
            }
            // base
            else {
                return this.techNameLookup[techId];
            }
        },

        enrichCartIfValid(cart) {
            // checks validity of cart, enriches if valid, returns validity bool
            // enriching means adding TechName and TactName (as JSON carts only store the IDs)

            // CALLER MUST CALL await Alpine.store('attackIDHelper').load(cart.version) BEFORE
            // Failure to do so will result in this failing out

            // version not on server (load takes care of doToast warning)
            if (this.loadedVersion != cart.version) {
                return false;
            }

            // invalid pairs
            const idPairsValid = cart.entries.every((e) => this.doesTactTechPairExist(e.tactic, e.index));
            if (!idPairsValid) {
                doToast('Cannot load this cart. It contains invalid Tactic + Technique pairs.', false);
                return false;
            }

            // cart is good -> enrich it
            cart.entries.forEach((e) => {
                e.name = this.getTechFullName(e.index);
                e.tacticName = this.tactNameLookup[e.tactic];
            });
            return true;
        },
    });

    Alpine.data('toast', function (data) {
        const timestamp = new Date().toLocaleString('en-US', {
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric',
            hour12: true,
        });
        return {
            success: data.success,
            bodyText: data.text,
            titleText: `${data.success ? 'Success' : 'Warning'} - ${timestamp}`,
        };
    });

    Alpine.data('scrollToTop', () => ({
        visible: false,
        onScroll() {
            this.visible = (document.body.scrollTop || document.documentElement.scrollTop) > 100;
        },
        onClick() {
            document.body.scrollTop = document.documentElement.scrollTop = 0;
            document.getElementById('skip-to-main-content').focus();
        },
    }));

    Alpine.data('questionTree', () => ({
        // |
        // | init
        // V
        answerCards: [], // ROM
        // |
        // | doFiltering
        // V
        filteredCards: [],
        // |
        // | doSearching
        // V
        searchedCards: [],
        // |
        // | doHighlighting
        // V
        highlightedCards: [],
        // |
        // | doPagination
        // V
        paginatedCards: [], // [[c, c, c], [c, c]] - do not show controls if only 1-page exists

        searchStatus: '',
        search: '',
        platforms: [],
        data_sources: [],
        page: 1,
        urlHash: '',

        async doFetchCards() {
            const globalStore = Alpine.store('global');
            const questionStore = Alpine.store('question');

            const response = await fetchV2({
                url: '/api/answers',
                params: {
                    index: questionStore.id,
                    tactic: questionStore.tactic,
                    version: globalStore.versionPicker.cur_version,
                },
            });

            if (response.netFail || !response.ok) {
                doToast('Failed to fetch answer cards. Please refresh.', false);
                return [];
            }

            return response.data;
        },

        async init() {
            const cards = await this.doFetchCards();
            cards.forEach((card, index) => {
                const d = document.createElement('div');
                d.innerHTML = card.content;

                card.score = -index; // ordering (default score)

                // minisearch
                card.content_text = d.textContent;
                card.label = `${card.name} [${card.id}]`;
            });

            this.answerCards = cards;

            // filter / search change -> reset page
            Alpine.effect(() => {
                let a = this.platforms;
                let b = this.data_sources;
                let c = this.search;
                this.page = 1;
            });

            // init search/filters/page from URL, then auto-update URL
            this.readHashParams();
            Alpine.effect(() => this.writeHashParams());

            // data pipeline
            Alpine.effect(() => this.doFiltering());
            Alpine.effect(() => this.doSearching());
            Alpine.effect(() => this.doHighlighting());
            Alpine.effect(() => this.doPagination());
        },

        doFiltering() {
            // answerCards ---> filteredCards

            let cards = this.answerCards;

            if (this.platforms.length > 0) {
                cards = cards.filter((card) => _.intersection(card.platforms, this.platforms).length > 0);
            }

            if (this.data_sources.length > 0) {
                cards = cards.filter((card) => _.intersection(card.data_sources, this.data_sources).length > 0);
            }

            this.filteredCards = cards;
        },

        async doSearching() {
            // filteredCards ---> searchedCards

            let cards = JSON.parse(JSON.stringify(this.filteredCards));

            // frontend MiniSearch
            if (Alpine.store('question').id === 'start') {
                const minSearchLength = 3;

                if (this.search.length < minSearchLength) {
                    // don't annoy with empty / insignificant search
                    this.searchStatus = '';
                } else if (this.search.length > 512) {
                    this.searchStatus = 'Search too long';
                } else {
                    const ms = new MiniSearch({ fields: ['label', 'content_text'] });
                    ms.addAll(cards);
                    const results = ms.search(this.search, {
                        prefix: (term) => term.length >= minSearchLength,
                        fuzzy: (term) => (term.length >= minSearchLength ? 0.15 : null),
                    });

                    const resultsIndex = {};
                    results.forEach((res) => (resultsIndex[res.id] = res));

                    if (results.length === 0) {
                        this.searchStatus = 'No matches - answers will stay in their default order';
                    } else {
                        // don't annoy when they can see it worked
                        this.searchStatus = '';
                        cards.forEach((card) => {
                            if (card.id in resultsIndex) {
                                const res = resultsIndex[card.id];
                                card.score = res.score;
                                card.display_matches = res.terms;
                                card.additional_matches = [];
                            }
                        });
                    }
                }
            }

            // backend PostgresFTS
            else {
                const globalStore = Alpine.store('global');
                const questionStore = Alpine.store('question');

                const response = await fetchV2({
                    url: '/search/answer_cards',
                    params: {
                        version: globalStore.versionPicker.cur_version,
                        index: questionStore.id,
                        tactic_context: questionStore.tactic,
                        search: this.search,
                        platforms: this.platforms,
                        data_sources: this.data_sources,
                    },
                });
                if (response.netFail || !response.ok) {
                    doToast('Failed to search answer cards. Please refresh.', false);
                    this.searchStatus =
                        'Failed to search answers. Please refresh. Answers will stay in their default order';
                    cards.sort((a, b) => b.score - a.score);
                    this.searchedCards = cards;
                    return;
                }

                const results = response.data.results;
                const status = response.data.status;

                if (typeof results === 'undefined') {
                    if (status === 'Search query empty') {
                        // don't annoy with empty search
                        this.searchStatus = '';
                    } else {
                        this.searchStatus = status;
                    }
                } else if (Object.keys(results).length === 0) {
                    this.searchStatus = 'No matches - answers will stay in their default order';
                } else {
                    // don't annoy when they can see it worked
                    this.searchStatus = '';
                    cards.forEach((card) => {
                        // no scoring / highlighting on "There was not enough context" card (baseTech->self)
                        if (card.id === questionStore.id) {
                            return;
                        }

                        if (card.id in results) {
                            const res = results[card.id];
                            card.score = res.score;
                            card.display_matches = res.display_matches;
                            card.additional_matches = res.additional_matches;
                        }
                    });
                }
            }

            cards.sort((a, b) => b.score - a.score);
            this.searchedCards = cards;
        },

        doHighlighting() {
            // searchedCards ---> highlightedCards

            const markjs_opts = Alpine.store('question').markjs_opts;

            let cards = this.searchedCards;

            cards.forEach((card) => {
                const display_matches = card.display_matches ?? [];

                if (display_matches.length > 0) {
                    card.label = $('<div></div>').append(card.label).mark(display_matches, markjs_opts).html();
                    card.content = $('<div></div>').append(card.content).mark(display_matches, markjs_opts).html();
                }

                // additional_matches -> handled in template itself
            });

            this.highlightedCards = cards;
        },

        doPagination() {
            if (Alpine.store('question').id === 'start') {
                this.paginatedCards = [this.highlightedCards];
            } else {
                this.paginatedCards = _.chunk(this.highlightedCards, 5);
            }
        },

        readHashParams() {
            const questionStore = Alpine.store('question');
            const validPlatforms = questionStore.platformFilters.items.map(({ value }) => value);
            const validDataSources = questionStore.dataSrcFilters.items.map(({ value }) => value);

            const params = new URLSearchParams(window.location.hash.slice(1));

            this.search = (params.get('search') ?? '').trim();
            this.platforms = _.intersection(params.getAll('platforms'), validPlatforms);
            this.data_sources = _.intersection(params.getAll('data_sources'), validDataSources);
        },

        writeHashParams() {
            this.urlHash = urlSearchParamsV2({
                search: this.search,
                platforms: this.platforms,
                data_sources: this.data_sources,
            });
            history.replaceState({}, '', `${getURLNoHash()}#${this.urlHash}`);
        },
    }));

    Alpine.data('successCoocs', () => ({
        showAllCoocs: false,

        loaded: false,

        coocs: [],
        coocsDisplayed: [],

        async init() {
            const response = await fetchV2({
                url: '/api/cooccurrences',
                params: {
                    version: Alpine.store('global').versionPicker.cur_version,
                    tech_ids: Alpine.store('success').id,
                },
            });

            if (response.netFail || !response.ok) {
                doToast('Failed to fetch "Frequently Appears With" data.', false);
            } else {
                const coocs = response.data;

                coocs.forEach((cooc) => {
                    // displayed when expanded
                    // cooc.tech_desc

                    // displayed when collapsed (prevents tabbing)
                    cooc.short_desc = $(cooc.tech_desc).text();
                });

                this.coocs = coocs;
                this.loaded = true;
                if (this.coocs.length > 0) {
                    Alpine.effect(() => this.updateDisplayed());
                }
            }
        },

        updateDisplayed() {
            // nothing to show
            if (this.coocs.length === 0) {
                return;
            }

            // show all
            if (this.showAllCoocs) {
                this.coocsDisplayed = this.coocs;
            }

            // show limited subset
            else {
                // Split into 2 arrays by score level: 2+, 1+ (<2)
                let over_2s = this.coocs.filter((c) => c.score >= 2.0);
                let over_1s = this.coocs.filter((c) => c.score < 2.0);

                // Determind num of entries to grab [5 default; 10 if there are >5 scores >=2]
                let max_entries = over_2s.length > 5 ? 10 : 5;

                let amt_2s = Math.min(max_entries, over_2s.length); // Try to fill max entries, get available at worst
                let amt_1s = Math.min(max_entries - amt_2s, over_1s.length); // Try to makeup difference, get available at worst

                let pulled_2s = _.sampleSize(over_2s, amt_2s); // Grab >= 2
                let pulled_1s = _.sampleSize(over_1s, amt_1s); // Grab >= 1 (<2)
                let combined = pulled_2s.concat(pulled_1s);

                // Re-order by score descending as prior operations change order
                combined.sort((a, b) => b.score - a.score);

                this.coocsDisplayed = combined;
            }
        },
    }));

    Alpine.data('collapseTracker', (defaultShow, persistName) => ({
        // defaultShow: boolean, required
        // persistName: string , optional

        show: defaultShow,

        init() {
            const collapseEl = this.$refs.collapse;

            // if persisted
            if (typeof persistName === 'string') {
                // get saved state
                const savedShow = localStorage.getItem(`collapse-${persistName}`);

                // state non-null -> set it
                if (typeof savedShow === 'string') {
                    this.show = Boolean(savedShow);
                }

                // auto-save
                Alpine.effect(() => {
                    const state = this.show ? '-truthy-string-' : '';
                    localStorage.setItem(`collapse-${persistName}`, state);
                });
            }

            if (this.show) {
                $(collapseEl).addClass('show');
            }

            new bootstrap.Collapse(collapseEl, { toggle: false });
        },

        binds: {
            ['@hide-bs-collapse.dot']() {
                this.show = false;
            },
            ['@shown-bs-collapse.dot']() {
                this.show = true;
            },
        },
    }));

    Alpine.data('successAddToCart', () => ({
        tacticId: null,

        init() {
            this.tacticId = Alpine.store('success').tactic_context;
        },

        addToCart() {
            const globals = Alpine.store('global');
            const success = Alpine.store('success');

            const tactic = success.tactics.filter((t) => t.tact_id === this.tacticId)[0];

            const fullTechName =
                success.base_tech.id === success.id ? success.name : `${success.base_tech.name}: ${success.name}`;

            this.$dispatch('add-to-cart', {
                version: globals.versionPicker.cur_version,
                entry: {
                    index: success.id,
                    name: fullTechName,
                    tactic: tactic.tact_id,
                    tacticName: tactic.tact_name,
                    notes: '',
                },
            });
        },
    }));

    Alpine.data('offcanvasCart', () => ({
        offcanvasBS: undefined,

        inTitleEditor: false,
        newTitleValid: false,
        newTitle: '',

        inCloseConfirm: false,

        title: '',
        version: '',
        entries: [],

        binds: {
            ['@shown-bs-offcanvas.dot']() {
                this.$refs.closeCart.focus();
            },
            ['@add-to-cart.window']() {
                const request = this.$event.detail;
                // request = {
                //     version: '',
                //     entry  : {
                //         index     : '',
                //         name      : '',
                //         tactic    : '',
                //         tacticName: '',
                //         notes     : '',
                //     }
                // }

                // version mismatch
                if (request.version !== this.version) {
                    doToast(
                        `You tried adding a Technique from Enterprise ${request.version}
                        to a Cart for Enterprise ${this.version}. This does not work.`,
                        false
                    );
                    return;
                }

                // add identifier for alpine
                request.entry.appId = uuidv4();

                this.entries.unshift(request.entry);
                this.offcanvasBS.show();
            },
        },

        hide() {
            this.offcanvasBS.hide();
        },

        show() {
            this.offcanvasBS.show();
        },

        toggle() {
            this.offcanvasBS.toggle();
        },

        init() {
            this.offcanvasBS = new bootstrap.Offcanvas(this.$root, {
                scroll: false,
                backdrop: true,
            });

            this.loadFromLocalStorage();

            // cart version doesn't match the page version
            const appVersion = Alpine.store('global').versionPicker.cur_version;
            if (this.version !== appVersion) {
                // cart has content -> warn user
                if (this.entries.length > 0) {
                    doToast(
                        `The page you are viewing is for Enterprise ${appVersion}, but you have an Enterprise ${this.version} cart open.`,
                        false
                    );
                }

                // cart is empty -> just swap it
                else {
                    this.version = appVersion;
                }
            }

            // autosave
            Alpine.effect(() => {
                const lsCart = {};
                cartFuncs.copyLSInterface(this, lsCart);
                localStorage.setItem('cart', JSON.stringify(lsCart));
            });

            // title editor validation
            Alpine.effect(() => {
                const nameChanged = this.title.trim() !== this.newTitle.trim();
                const nameHasLeng = this.newTitle.trim().length > 0;
                this.newTitleValid = nameChanged && nameHasLeng;
            });
        },

        loadFromLocalStorage() {
            try {
                const lsCart = JSON.parse(localStorage.getItem('cart'));
                if (!validate.hasLSCartInterface(lsCart)) {
                    throw new Error("Couldn't load cart from localStorage");
                }
                lsCart.entries.forEach((e) => {
                    e.appId = uuidv4();
                });
                cartFuncs.copyRAMInterface(lsCart, this);
            } catch {
                this.resetCart();
            }
        },

        resetCart() {
            this.title = 'Un-named';
            this.version = Alpine.store('global').versionPicker.cur_version;
            this.entries = [];

            this.inTitleEditor = false;
            this.newTitleValid = false;
            this.newTitle = '';
        },

        editTitleBegin() {
            this.newTitle = this.title;
            this.inTitleEditor = true;
            this.$nextTick(() => {
                document.getElementById('cartEditNameInput').focus();
            });
        },

        editTitleSave() {
            this.title = this.newTitle.trim();
            this.newTitle = '';
            this.inTitleEditor = false;
            this.$nextTick(() => {
                document.getElementById('cartEditNameButton').focus();
            });
        },

        editTitleCancel() {
            this.newTitle = '';
            this.inTitleEditor = false;
            this.$nextTick(() => {
                document.getElementById('cartEditNameButton').focus();
            });
        },

        saveToJson() {
            if (this.entries.length === 0) {
                doToast('You need at least 1 entry in order to save the cart.', false);
                return;
            }

            const jsonCart = {};
            cartFuncs.copyJSONInterface(this, jsonCart);
            const serial = JSON.stringify(jsonCart, null, 4);
            const name = `Cart_${this.title}_${this.version}.json`;
            try {
                const file = new Blob([serial], {
                    type: 'application/JSON',
                    name: name,
                });
                saveAs(file, name);
            } catch {
                doToast('Failed to save cart as a JSON file.', false);
            }
        },

        loadFromJson() {
            // button -> trigger <input> file selector
            document.getElementById('cartFile').click();
        },

        loadFromJsonFileChanged(inputEl) {
            // get <input> file
            const file = inputEl.files[0];
            if (!file) {
                doToast('Error loading cart - file invalid.', false);
                return;
            }

            // read file text -> loadFromJsonFileLoaded(e)
            const reader = new FileReader();
            reader.onload = (loadEvent) => {
                this.loadFromJsonFileLoaded(loadEvent);
            };
            reader.onerror = () => {
                doToast('Error loading cart - issue loading file content.', false);
            };
            reader.readAsText(file);
        },

        async loadFromJsonFileLoaded(loadEvent) {
            // get text -> json parse
            const text = loadEvent.target.result;
            let jsonData;
            try {
                jsonData = JSON.parse(text);
            } catch {
                doToast('Error loading cart - cart provided is not valid JSON.', false);
                return;
            }

            // check that it has fields a JSON-level cart should have
            if (!validate.hasJSONCartInterface(jsonData)) {
                doToast('Error loading cart - cart is missing expected fields / structure.', false);
                return;
            }

            // copy JSON-level fields only (prevents keeping extra data)
            const jsonCart = {};
            cartFuncs.copyJSONInterface(jsonData, jsonCart);

            // attempt loading ATT&CK data needed to validate this version cart
            const attackIDHelper = Alpine.store('attackIDHelper');
            await attackIDHelper.load(jsonCart.version);

            // validate the cart (enriching JSON -> LocalStorage by adding Tech/Tact names if successful)
            const isCartValid = attackIDHelper.enrichCartIfValid(jsonCart);
            if (!isCartValid) {
                // fail toasts provided by attackIDHelper.load / attackIDHelper.enrichCartIfValid
                return;
            }

            // enrich LocalStorage -> RAM by adding appId's for Alpine
            jsonCart.entries.forEach((e) => {
                e.appId = uuidv4();
            });

            // copy cart into Alpine
            cartFuncs.copyRAMInterface(jsonCart, this);
            doToast('Successfully loaded the cart file!', true);
        },

        async exportToWordDoc() {
            if (this.entries.length === 0) {
                doToast('You need at least 1 entry in order to export the cart to docx.', false);
                return;
            }

            // ask server to validate / order / get names+urls for cart entries
            const redactCart = {};
            cartFuncs.copyRedactInterface(this, redactCart);
            const response = await fetchV2({
                type: 'POST',
                url: '/api/sort_cart',
                body: redactCart,
            });
            if (response.netFail || !response.ok) {
                doToast(
                    'Failed to export Word Doc: could not ask server for help ordering / validating entries.',
                    false
                );
                return;
            }
            const tactsAndTechs = response.data;

            // lookup table for mapping notes
            const lookupUsage = {};
            this.entries.forEach((e) => {
                const techId = e.index;
                const tactId = e.tactic;
                const key = `${tactId}--${techId}`;
                lookupUsage[key] = lookupUsage[key] ?? [];
                lookupUsage[key].push(e.notes);
            });

            // generate report
            let report;
            try {
                report = docxHelpers.generateReport({
                    tactsAndTechs: tactsAndTechs,
                    lookupUsage: lookupUsage,
                    attackVersion: `Enterprise ${this.version}`,
                    deciderVersion: Alpine.store('global').appVersion,
                    reportName: this.title,
                });
            } catch {
                doToast('Failed to export Word Doc: issue during generation.', false);
                return;
            }

            // download report
            try {
                docx.Packer.toBlob(report).then((blob) => {
                    saveAs(blob, `Word_${this.title}_${this.version}.docx`);
                });
            } catch {
                doToast('Failed to export Word Doc: issue during file saving.', false);
            }
        },

        exportToNavLayer() {
            if (this.entries.length === 0) {
                doToast('You need at least 1 entry in order to export the cart to a Navigator layer.', false);
                return;
            }

            // Considerations
            // ______________
            // - tacticName.toLowerCase().replaceAll(" ", "-") is being used as x_mitre_shortname, might not always apply
            // - versions.[navigator, layer] need to be manually updated
            // - platforms are currently hardcoded for enterprise (same as .domain)
            //   - when doing multi-domain support, add /api/platform(s) route and GET that

            // Future Polish
            // _____________
            // IDEA: perhaps a lighter highlight too as partial coverage exists

            const keyToComments = {}; // str -> str[]   | absent key means unmapped
            const keyToShowSubs = {}; // str -> boolean | absent key means false

            // record existence / parent showSubs for each entry
            this.entries.forEach(({ index, tacticName, notes }) => {

                const techId = index;
                const tactShortname = tacticName.toLowerCase().replaceAll(' ', '-');
                const comment = notes.trim();
                const key = `${techId}--${tactShortname}`;

                // tech is a sub
                if (techId.includes('.')) {
                    const baseId = techId.split('.')[0];
                    const baseKey = `${baseId}--${tactShortname}`;

                    // mark parent shows subs
                    keyToShowSubs[baseKey] = true;
                }

                // mark exists
                keyToComments[key] = keyToComments[key] ?? [];

                // add comment if present
                if (comment.length > 0) {
                    keyToComments[key].push(comment);
                }
            });

            const allKeys = Array.from(new Set([
                ...Object.keys(keyToComments),
                ...Object.keys(keyToShowSubs)
            ]));

            const techniques = allKeys.map((key) => {

                const [techId, tactShortname] = key.split('--');
                const exists = typeof keyToComments[key] !== 'undefined';
                const color = exists ? '#e60d0d' : '';
                const comment = exists ? (keyToComments[key].join(',\n') || '-no comment-') : '';
                const showSubs = keyToShowSubs[key] ?? false;

                return {
                    techniqueID: techId,
                    tactic: tactShortname,
                    color: color,
                    comment: comment,
                    enabled: true,
                    metadata: [],
                    links: [],
                    showSubtechniques: showSubs
                };
            });

            // base structure
            let navigatorJSON = {
                name: 'layer',
                versions: {
                    attack: this.version.replaceAll('v', '').split(".")[0], // vX.Y -> X
                    navigator: '4.9.1',
                    layer: '4.5',
                },
                domain: 'enterprise-attack',
                description: '',
                filters: {
                    platforms: [
                        'Linux',
                        'macOS',
                        'Windows',
                        'Azure AD',
                        'Office 365',
                        'SaaS',
                        'IaaS',
                        'Google Workspace',
                        'PRE',
                        'Network',
                        'Containers',
                    ],
                },
                sorting: 0,
                layout: {
                    layout: 'side',
                    aggregateFunction: 'average',
                    showID: false,
                    showName: true,
                    showAggregateScores: false,
                    countUnscored: false,
                    expandedSubtechniques: 'annotated'
                },
                hideDisabled: false,
                techniques: techniques,
                gradient: {
                    colors: [
                        "#ff6666ff",
                        "#ffe766ff",
                        "#8ec843ff"
                    ],
                    minValue: 0,
                    maxValue: 100
                },
                legendItems: [],
                metadata: [],
                links: [],
                showTacticRowBackground: false,
                tacticRowBackground: "#dddddd",
                selectTechniquesAcrossTactics: false,
                selectSubtechniquesWithParent: false,
                selectVisibleTechniques: false
            };

            // dump it
            const serial = JSON.stringify(navigatorJSON);
            const name = `Navigator_${this.title}_${this.version}.json`;
            try {
                const file = new Blob([serial], {
                    type: 'application/JSON',
                    name: name,
                });
                saveAs(file, name);
            } catch {
                doToast('Failed to save cart as an ATT&CK Navigator Layer file.', false);
            }
        },

        closeCartBegin() {
            this.inCloseConfirm = true;
            this.$nextTick(() => {
                document.getElementById('closeCartCancelButton').focus();
            });
        },

        closeCartConfirm() {
            this.inCloseConfirm = false;
            this.resetCart();
            this.$nextTick(() => {
                document.getElementById('closeCartBeginButton').focus();
            });
        },

        closeCartCancel() {
            this.inCloseConfirm = false;
            this.$nextTick(() => {
                document.getElementById('closeCartBeginButton').focus();
            });
        },
    }));

    Alpine.data('cartwideCoocs', () => ({
        cart: {},
        coocs: [],
        loaded: false,
        statusMessages: [],

        pageVersion: Alpine.store('global').versionPicker.cur_version,

        async init() {
            // load cart and coocs for it
            if (!this.loadCartFromLocalStorage()) {
            } else if (this.cart.entries.length === 0) {
                // no coocs to load for 0 items
                this.loaded = true;
            } else {
                const response = await fetchV2({
                    url: '/api/cooccurrences',
                    params: {
                        version: this.cart.version,
                        tech_ids: this.cart.entries.map((e) => e.index),
                    },
                });
                if (response.netFail || !response.ok) {
                    doToast('Failed to fetch "Frequently Appears With" data for cart entries', false);
                } else {
                    const coocs = response.data;

                    coocs.forEach((cooc) => {
                        // displayed when expanded
                        // cooc.tech_desc

                        // displayed when collapsed (prevents tabbing)
                        cooc.short_desc = $(cooc.tech_desc).text();
                    });

                    this.coocs = coocs;
                    this.loaded = true;
                }
            }

            // build status message(s) here
            if (this.loaded) {
                // empty cart
                if (this.cart.entries.length === 0) {
                    this.statusMessages.push('Your cart has 0 items, and thus no frequently appearing Techniques.');
                }

                // populated cart - but no coocs
                else if (this.coocs.length === 0) {
                    this.statusMessages.push(
                        'Your cart has items, but there are no frequently appearing Techniques for them.'
                    );
                }

                // version mismatch
                if (this.cart.version !== this.pageVersion) {
                    this.statusMessages.push(
                        `
                        You're on the suggestions page for Enterprise ${this.pageVersion}, while your cart has content for
                        Enterprise ${this.cart.version}. No worries - as content was loaded based off of your cart.
                    `.trim()
                    );
                }
            } else {
                this.statusMessages.push('Failed to load both the Cart & frequently appearing Techniques for it.');
            }
        },

        loadCartFromLocalStorage() {
            try {
                const lsCart = JSON.parse(localStorage.getItem('cart'));
                if (!validate.hasLSCartInterface(lsCart)) {
                    throw new Error("Couldn't load cart from localStorage");
                }
                lsCart.entries.forEach((e) => {
                    e.appId = uuidv4();
                });
                cartFuncs.copyRAMInterface(lsCart, this.cart);
                return true;
            } catch {
                doToast('Failed to load cart from localStorage for "Frequently Appears With".', false);
                return false;
            }
        },
    }));

    Alpine.data('navMiniSearch', () => ({
        search: '',
        techniques: [],
        version: Alpine.store('global').versionPicker.cur_version,
        focused: false,

        // dynamically recalculated according to search entered
        fullSearchUrl: resolveURL('/'),

        init() {
            // initial blank search
            this.fullSearchUrl = resolveURL(
                '/search/page?' + urlSearchParamsV2({ version: this.version, search: '' })
            );

            Alpine.effect(() => {
                this.update();
            });
        },

        async update() {
            const search = this.search.trim();

            // run search
            this.techniques = [];
            if (search.length < 2) {
                return;
            }

            const response = await fetchV2({
                url: `/search/mini/${encodeURIComponent(this.version)}`,
                type: 'POST',
                body: { search: search },
            });
            if (response.netFail || !response.ok) {
                doToast('Failed to search Technique Names/IDs. Please refresh.', false);
                return;
            }

            const techniques = response.data;

            techniques.forEach((t) => {
                const fullName = t.tech_name;
                const techId = t.tech_id;
                delete t.tech_name;
                delete t.tech_id;

                let isSub = techId.includes('.');
                let baseName;
                let subName;

                // sub
                if (isSub) {
                    [baseName, subName] = fullName.split(':', 2);
                    subName = subName.trim();
                }
                // base
                else {
                    baseName = fullName;
                    subName = '';
                }

                t.isSub = isSub;
                t.baseName = baseName;
                t.subName = subName;
                t.techId = techId;
            });
            this.techniques = techniques;
        },

        onFocus() {
            if (!this.$root.contains(this.$event.relatedTarget)) {
                this.focused = true;
                this.$nextTick(() => {
                    $('#navMiniSearchDropdown').scrollTop(0);
                });
            }
        },

        onBlur() {
            if (!this.$root.contains(this.$event.relatedTarget)) {
                this.focused = false;
            }
        },

        onInput() {
            this.focused = true;

            // update full search target
            // (handled onInput as this isn't debounced, only results get deplayed, not [Enter] / fullsearch link usage)
            const fullSearchParams = urlSearchParamsV2({
                version: this.version,
                search: this.$el.value.trim(),
            });
            this.fullSearchUrl = resolveURL(`/search/page?${fullSearchParams}`);
        },

        onEscape() {
            // visual toggle...
            this.focused = !this.focused;

            // but keep us there for tabbing
            $('#navMiniSearchInput').focus();
        },

        onEnterInput() {
            window.location.href = this.fullSearchUrl;
        },

        onUpList() {
            const prevItems = $(':focus').parent().prevAll('li');

            // items before us -> go to prev
            if (prevItems.length > 0) {
                const prevItem = $(prevItems.get(0));
                const prevLink = prevItem.children().get(0);
                prevLink.focus({ preventScroll: true });
                const dropdown = $('#navMiniSearchDropdown');
                dropdown.scrollTop(prevItem.offset().top - dropdown.offset().top + dropdown.scrollTop());
            }

            // nothing before us -> go to input bar
            else {
                $('#navMiniSearchInput').focus();
            }
        },

        onTabList() {
            this.focused = false;
        },

        onDownList() {
            const nextItems = $(':focus').parent().nextAll('li');
            if (nextItems.length > 0) {
                const nextItem = $(nextItems.get(0));
                const itemLink = nextItem.children().get(0);
                itemLink.focus({ preventScroll: true });
                const dropdown = $('#navMiniSearchDropdown');
                dropdown.scrollTop(nextItem.offset().top - dropdown.offset().top + dropdown.scrollTop());
            }
        },

        onDownInput() {
            // ensure focused (reset [Escape] press basically)
            this.focused = true;

            // when rendered -> jump to first item in list
            this.$nextTick(() => {
                const firstItem = $($('#navMiniSearchDropdownList').children().get(0));
                const firstLink = firstItem.children().get(0);
                firstLink.focus({ preventScroll: true });
                const dropdown = $('#navMiniSearchDropdown');
                dropdown.scrollTop(firstItem.offset().top - dropdown.offset().top + dropdown.scrollTop());
            });
        },
    }));

    Alpine.data('fullSearchPage', () => ({
        version: '',
        search: '',
        searchStatus: '',
        tactics: [],
        platforms: [],
        data_sources: [],

        results: [],

        init() {
            // initial URL read -> then auto write it & auto search
            this.readUrlParams();
            Alpine.effect(() => this.writeUrlParams());
            Alpine.effect(() => this.doSearch());
        },

        readUrlParams() {
            const url = new URL(window.location.href);
            this.version = url.searchParams.get('version');
            this.search = url.searchParams.get('search');
            this.tactics = url.searchParams.getAll('tactics');
            this.platforms = url.searchParams.getAll('platforms');
            this.data_sources = url.searchParams.getAll('data_sources');
        },

        writeUrlParams() {
            const urlNoParam = window.location.href.split('?')[0];
            const paramStr = urlSearchParamsV2({
                version: this.version,
                search: this.search,
                tactics: this.tactics,
                platforms: this.platforms,
                data_sources: this.data_sources,
            });
            history.replaceState({}, '', `${urlNoParam}?${paramStr}`);
        },

        async doSearch() {
            const response = await fetchV2({
                url: '/search/full',
                params: {
                    version: this.version,
                    search: this.search,
                    tactics: this.tactics,
                    platforms: this.platforms,
                    data_sources: this.data_sources,
                },
            });
            if (response.netFail) {
                doToast('Failed to perform search due to network issue. Please refresh.', false);
                return;
            }
            if (!response.ok) {
                const message = response.data.message ?? 'Unknown error';
                doToast(`Search Failed: ${message}`, false);
                return;
            }
            const data = response.data;

            // don't annoy user if they haven't typed anything
            if (data.status === 'Please type a search query') {
                this.searchStatus = '';
            } else {
                this.searchStatus = data.status;
            }
            this.results = data.techniques;
        },
    }));
});

// Format validator function namespace
window.validate = {};

validate.isTactID = function (text) {
    return /^TA[0-9]{4}$/.test(text);
};

validate.isTechID = function (text) {
    return /^T[0-9]{4}(?:\.[0-9]{3})?$/.test(text);
};

validate.isVersion = function (text) {
    return /^v[0-9]{1,10}\.[0-9]{1,10}$/.test(text);
};

validate.hasJSONCartEntryInterface = function (entry) {
    // cart entries from JSON need these fields

    // {}
    if (!_.isPlainObject(entry)) return false;

    // .index: 'Tabcd(.xyz)?'
    if (!_.isString(entry.index)) return false;
    if (!validate.isTechID(entry.index)) return false;

    // .tactic: 'TAabcd'
    if (!_.isString(entry.tactic)) return false;
    if (!validate.isTactID(entry.tactic)) return false;

    // .notes: '...'
    if (!_.isString(entry.notes)) return false;

    return true;
};

validate.hasJSONCartInterface = function (cart) {
    // carts from JSON need these fields

    // {}
    if (!_.isPlainObject(cart)) return false;

    // .title: 'has length'
    if (!_.isString(cart.title)) return false;
    if (cart.title.length === 0) return false;

    // .version: 'vX.Y'
    if (!_.isString(cart.version)) return false;
    if (!validate.isVersion(cart.version)) return false;

    // .entries: CartEntry[]
    if (!_.isArray(cart.entries)) return false;
    if (!cart.entries.every(validate.hasJSONCartEntryInterface)) return false;

    return true;
};

validate.hasLSCartEntryInterface = function (entry) {
    // cart entries from localStorage need these fields (superset of JSON interface)

    if (!validate.hasJSONCartEntryInterface(entry)) return false;

    // .name: 'has length'
    if (!_.isString(entry.name)) return false;
    if (entry.name.length === 0) return false;

    // .tacticName: 'has length'
    if (!_.isString(entry.tacticName)) return false;
    if (entry.tacticName.length === 0) return false;

    return true;
};

validate.hasLSCartInterface = function (cart) {
    // carts from localStorage need these fields (superset of JSON interface)

    // {}
    if (!_.isPlainObject(cart)) return false;

    // .title: 'has length'
    if (!_.isString(cart.title)) return false;
    if (cart.title.length === 0) return false;

    // .version: 'vX.Y'
    if (!_.isString(cart.version)) return false;
    if (!validate.isVersion(cart.version)) return false;

    // .entries: CartEntry[]
    if (!_.isArray(cart.entries)) return false;
    if (!cart.entries.every(validate.hasLSCartEntryInterface)) return false;

    return true;
};

// Cart helper function namespace
window.cartFuncs = {};

cartFuncs.copyJSONInterface = function (src, dest) {
    // copies minimal fields covering JSON-level cart interface

    dest.title = src.title;
    dest.version = src.version;
    dest.entries = src.entries.map(({ index, tactic, notes }) => ({ index, tactic, notes }));
};

cartFuncs.copyLSInterface = function (src, dest) {
    // copies minimal fields covering localStorage-level cart interface

    dest.title = src.title;
    dest.version = src.version;
    dest.entries = src.entries.map(({ index, tactic, notes, name, tacticName }) => ({
        index,
        tactic,
        notes,
        name,
        tacticName,
    }));
};

cartFuncs.copyRAMInterface = function (src, dest) {
    // copies minimal fields covering memory-level cart interface
    // (LS, but with appId's for Alpine keys)

    dest.title = src.title;
    dest.version = src.version;
    dest.entries = src.entries.map(({ index, tactic, notes, name, tacticName, appId }) => ({
        index,
        tactic,
        notes,
        name,
        tacticName,
        appId,
    }));
};

cartFuncs.copyRedactInterface = function (src, dest) {
    // copies minimal fields needed for /api/sort_cart to validate cart entry existence

    dest.version = src.version;
    dest.entries = src.entries.map(({ index, tactic }) => ({ index, tactic }));
};

// docx report function namespace
window.docxHelpers = {};

docxHelpers.hyperlinkParagraph = function (args) {
    const par = new docx.Paragraph({
        alignment: args.alignment,
        children: [
            new docx.ExternalHyperlink({
                children: [
                    new docx.TextRun({
                        text: args.text,
                        style: 'Hyperlink',
                        bold: args.bold,
                        color: args.color,
                    }),
                ],
                link: args.link,
            }),
        ],
    });

    return par;
};

docxHelpers.generateReport = function (args) {
    const tactsAndTechs = args.tactsAndTechs;
    const lookupUsage = args.lookupUsage;
    const attackVersion = args.attackVersion;
    const deciderVersion = args.deciderVersion;
    const reportName = args.reportName;

    // column width spacing params - active page space is 9028 units wide
    const TECH_NAME_COL_W = 3000;
    const TECH_ID_COL_W = 1500;
    const TECH_USES_COL_W = 9028 - TECH_NAME_COL_W - TECH_ID_COL_W;

    const tableRows = [];

    // loop through tactics in cart
    tactsAndTechs.forEach((tactRow) => {
        const [tactId, tactName, tactUrl, techRows] = tactRow;

        // tactic header
        tableRows.push(
            new docx.TableRow({
                height: {
                    value: 400,
                    rule: docx.HeightRule.EXACT,
                },
                children: [
                    new docx.TableCell({
                        width: {
                            size: 9028,
                            type: docx.WidthType.DXA,
                        },
                        columnSpan: 3,
                        verticalAlign: docx.VerticalAlign.CENTER,
                        shading: {
                            fill: '444444',
                            type: docx.ShadingType.SOLID,
                            color: '444444',
                        },
                        children: [
                            docxHelpers.hyperlinkParagraph({
                                text: `${tactName} [${tactId}]`,
                                link: tactUrl,
                                bold: true,
                                color: '00bbee',
                                alignment: docx.AlignmentType.CENTER,
                            }),
                        ],
                    }),
                ],
            })
        );

        // technique header
        const techHeaderTextsWidths = [
            { text: 'Technique Name', width: TECH_NAME_COL_W },
            { text: 'ID', width: TECH_ID_COL_W },
            { text: 'Use(s)', width: TECH_USES_COL_W },
        ];
        tableRows.push(
            new docx.TableRow({
                height: {
                    value: 400,
                    rule: docx.HeightRule.EXACT,
                },
                children: techHeaderTextsWidths.map(
                    (cellData) =>
                        new docx.TableCell({
                            width: {
                                size: cellData.width,
                                type: docx.WidthType.DXA,
                            },
                            shading: {
                                fill: '888888',
                                type: docx.ShadingType.SOLID,
                                color: '888888',
                            },
                            verticalAlign: docx.VerticalAlign.CENTER,
                            children: [
                                new docx.Paragraph({
                                    alignment: docx.AlignmentType.CENTER,
                                    children: [
                                        new docx.TextRun({
                                            text: cellData.text,
                                            bold: true,
                                            color: 'ffffff',
                                        }),
                                    ],
                                }),
                            ],
                        })
                ),
            })
        );

        // loop through techs of tactic
        techRows.forEach((techRow) => {
            const [techId, techName, techUrl] = techRow;
            const usages = lookupUsage[`${tactId}--${techId}`] ?? [];

            // look through usages in tact-tech pair
            usages.forEach((usage, index) => {
                const rowCells = [];

                // first row gets spanned Tech Name & Tech ID cells
                if (index === 0) {
                    rowCells.push(
                        ...[
                            new docx.TableCell({
                                verticalAlign: docx.VerticalAlign.CENTER,
                                rowSpan: usages.length,
                                children: [new docx.Paragraph(techName)],
                            }),
                            new docx.TableCell({
                                verticalAlign: docx.VerticalAlign.CENTER,
                                rowSpan: usages.length,
                                children: [
                                    docxHelpers.hyperlinkParagraph({
                                        text: techId,
                                        link: techUrl,
                                        bold: true,
                                        alignment: docx.AlignmentType.CENTER,
                                    }),
                                ],
                            }),
                        ]
                    );
                }

                // all rows get usage
                rowCells.push(
                    new docx.TableCell({
                        children: [new docx.Paragraph(usage || '-')],
                    })
                );

                // add row
                tableRows.push(
                    new docx.TableRow({
                        children: rowCells,
                    })
                );
            });
        });
    });

    // header text
    const docHeaderParagraphs = [
        new docx.Paragraph({
            children: [
                new docx.TextRun({ text: 'Report Name:', bold: true }),
                new docx.TextRun({ text: ` ${reportName}\n` }),
            ],
        }),
        new docx.Paragraph({
            children: [
                new docx.TextRun({ text: 'ATT&CK Version:', bold: true }),
                new docx.TextRun({ text: ` ${attackVersion}\n` }),
            ],
        }),
        new docx.Paragraph({
            children: [
                new docx.TextRun({ text: 'Decider Version:', bold: true }),
                new docx.TextRun({ text: ` ${deciderVersion}\n` }),
            ],
        }),
        new docx.Paragraph({
            spacing: {
                after: 400,
            },
            children: [
                new docx.TextRun({ text: 'Cart Export Time:', bold: true }),
                new docx.TextRun({ text: ` ${new Date().toString()}\n` }),
            ],
        }),
    ];

    // document
    const doc = new docx.Document({
        sections: [
            {
                children: [
                    ...docHeaderParagraphs,
                    new docx.Table({
                        width: {
                            size: 9028,
                            type: docx.WidthType.DXA,
                        },
                        rows: tableRows,
                    }),
                ],
            },
        ],
    });

    return doc;
};
