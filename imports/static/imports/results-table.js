"use strict";

(() => {
    const initialDataElement = document.getElementById("analysis-page-data");
    if (!initialDataElement) {
        return;
    }

    const initialPages = JSON.parse(initialDataElement.textContent);

    const renderCell = (cell, value) => {
        if (Array.isArray(value)) {
            const list = document.createElement("ul");
            value.forEach((item) => {
                const listItem = document.createElement("li");
                listItem.textContent = item;
                list.append(listItem);
            });
            cell.append(list);
            return;
        }

        cell.textContent = value === "" || value === null || value === undefined
            ? "—"
            : String(value);
    };

    document.querySelectorAll("[data-table-endpoint]").forEach((container) => {
        const tableKey = container.dataset.tableKey;
        const endpoint = container.dataset.tableEndpoint;
        const searchInput = container.querySelector('[data-role="search"]');
        const pageSizeSelect = container.querySelector('[data-role="page-size"]');
        const body = container.querySelector('[data-role="body"]');
        const tableWrap = container.querySelector('[data-role="table-wrap"]');
        const emptyMessage = container.querySelector('[data-role="empty"]');
        const summary = container.querySelector('[data-role="summary"]');
        const pageLabel = container.querySelector('[data-role="page-label"]');
        const previousButton = container.querySelector('[data-role="previous"]');
        const nextButton = container.querySelector('[data-role="next"]');
        const pagination = container.querySelector('[data-role="pagination"]');
        const sortButtons = Array.from(
            container.querySelectorAll("[data-sort-key]"),
        );

        const state = {
            abortController: null,
            direction: "ascending",
            page: 1,
            pageCount: 0,
            pageSize: Number(pageSizeSelect.value),
            query: "",
            sortKey: "",
        };

        const updateSortIndicators = () => {
            sortButtons.forEach((button) => {
                const active = button.dataset.sortKey === state.sortKey;
                const header = button.closest("th");
                const indicator = button.querySelector("[data-sort-indicator]");

                header.setAttribute(
                    "aria-sort",
                    active ? state.direction : "none",
                );
                indicator.textContent = active
                    ? (state.direction === "ascending" ? " ▲" : " ▼")
                    : "";
            });
        };

        const displayPage = (data) => {
            state.page = data.page || 1;
            state.pageCount = data.page_count;

            const fragment = document.createDocumentFragment();
            data.rows.forEach((row) => {
                const tableRow = document.createElement("tr");
                sortButtons.forEach((button) => {
                    const cell = document.createElement("td");
                    renderCell(cell, row[button.dataset.sortKey]);
                    tableRow.append(cell);
                });
                fragment.append(tableRow);
            });
            body.replaceChildren(fragment);

            const hasRows = data.rows.length > 0;
            tableWrap.hidden = !hasRows;
            pagination.hidden = !hasRows;
            emptyMessage.hidden = hasRows;
            emptyMessage.textContent = data.total === 0 && state.query
                ? "No rows match the current search."
                : emptyMessage.dataset.emptyMessage;
            summary.textContent = hasRows
                ? `${data.first}–${data.last} of ${data.total} rows`
                : (state.query ? "0 matching rows" : "0 rows");
            pageLabel.textContent = hasRows
                ? `Page ${data.page} of ${data.page_count}`
                : "Page 0 of 0";
            previousButton.disabled = !hasRows || data.page <= 1;
            nextButton.disabled = !hasRows || data.page >= data.page_count;
            updateSortIndicators();
        };

        const displayLoadError = () => {
            body.replaceChildren();
            tableWrap.hidden = true;
            pagination.hidden = true;
            emptyMessage.hidden = false;
            emptyMessage.textContent = "The result page could not be loaded. Please try again.";
            summary.textContent = "Load failed";
        };

        const loadPage = async () => {
            if (state.abortController) {
                state.abortController.abort();
            }
            const abortController = new AbortController();
            state.abortController = abortController;
            container.setAttribute("aria-busy", "true");
            summary.textContent = "Loading…";

            const url = new URL(endpoint, window.location.origin);
            url.searchParams.set("page", String(state.page));
            url.searchParams.set("page_size", String(state.pageSize));
            if (state.query) {
                url.searchParams.set("q", state.query);
            }
            if (state.sortKey) {
                url.searchParams.set("sort", state.sortKey);
                url.searchParams.set("direction", state.direction);
            }

            try {
                const response = await window.fetch(url, {
                    headers: {"Accept": "application/json"},
                    signal: abortController.signal,
                });
                if (!response.ok) {
                    throw new Error(`Result request failed with ${response.status}`);
                }
                displayPage(await response.json());
            } catch (error) {
                if (error.name !== "AbortError") {
                    displayLoadError();
                }
            } finally {
                if (state.abortController === abortController) {
                    container.removeAttribute("aria-busy");
                }
            }
        };

        let searchTimer;
        searchInput.addEventListener("input", () => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => {
                state.query = searchInput.value.trim();
                state.page = 1;
                loadPage();
            }, 250);
        });

        pageSizeSelect.addEventListener("change", () => {
            state.pageSize = Number(pageSizeSelect.value);
            state.page = 1;
            loadPage();
        });

        previousButton.addEventListener("click", () => {
            state.page = Math.max(1, state.page - 1);
            loadPage();
        });

        nextButton.addEventListener("click", () => {
            state.page = Math.min(state.pageCount, state.page + 1);
            loadPage();
        });

        sortButtons.forEach((button) => {
            button.addEventListener("click", () => {
                if (state.sortKey === button.dataset.sortKey) {
                    state.direction = state.direction === "ascending"
                        ? "descending"
                        : "ascending";
                } else {
                    state.sortKey = button.dataset.sortKey;
                    state.direction = "ascending";
                }
                state.page = 1;
                loadPage();
            });
        });

        const initialPage = initialPages[tableKey];
        displayPage(initialPage);
        const hasRows = initialPage.total > 0;
        searchInput.disabled = !hasRows;
        pageSizeSelect.disabled = !hasRows;
        container.dataset.enhanced = "true";
    });
})();
