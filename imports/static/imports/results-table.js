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
        const firstButton = container.querySelector('[data-role="first"]');
        const previousButton = container.querySelector('[data-role="previous"]');
        const nextButton = container.querySelector('[data-role="next"]');
        const lastButton = container.querySelector('[data-role="last"]');
        const pageNumbers = container.querySelector('[data-role="page-numbers"]');
        const jumpForm = container.querySelector('[data-role="jump-form"]');
        const jumpInput = container.querySelector('[data-role="jump-input"]');
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

        const visiblePageItems = (currentPage, pageCount) => {
            if (pageCount <= 7) {
                return Array.from({length: pageCount}, (_, index) => index + 1);
            }

            let rangeStart = Math.max(2, currentPage - 1);
            let rangeEnd = Math.min(pageCount - 1, currentPage + 1);
            if (currentPage <= 4) {
                rangeEnd = 5;
            }
            if (currentPage >= pageCount - 3) {
                rangeStart = pageCount - 4;
            }

            const items = [1];
            if (rangeStart > 2) {
                items.push("start-ellipsis");
            }
            for (let page = rangeStart; page <= rangeEnd; page += 1) {
                items.push(page);
            }
            if (rangeEnd < pageCount - 1) {
                items.push("end-ellipsis");
            }
            items.push(pageCount);
            return items;
        };

        const renderPageNumbers = (currentPage, pageCount) => {
            const fragment = document.createDocumentFragment();
            visiblePageItems(currentPage, pageCount).forEach((item) => {
                if (typeof item !== "number") {
                    const ellipsis = document.createElement("span");
                    ellipsis.className = "page-ellipsis";
                    ellipsis.textContent = "…";
                    ellipsis.setAttribute("aria-hidden", "true");
                    fragment.append(ellipsis);
                    return;
                }

                const button = document.createElement("button");
                button.type = "button";
                button.className = "page-number";
                button.textContent = String(item);
                button.setAttribute("aria-label", `Go to page ${item}`);
                if (item === currentPage) {
                    button.setAttribute("aria-current", "page");
                    button.disabled = true;
                } else {
                    button.addEventListener("click", () => {
                        state.page = item;
                        loadPage(true);
                    });
                }
                fragment.append(button);
            });
            pageNumbers.replaceChildren(fragment);
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
            firstButton.disabled = !hasRows || data.page <= 1;
            previousButton.disabled = !hasRows || data.page <= 1;
            nextButton.disabled = !hasRows || data.page >= data.page_count;
            lastButton.disabled = !hasRows || data.page >= data.page_count;
            jumpInput.disabled = !hasRows;
            jumpInput.max = String(Math.max(1, data.page_count));
            jumpInput.placeholder = hasRows ? String(data.page) : "";
            renderPageNumbers(data.page, data.page_count);
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

        const loadPage = async (scrollToTable = false) => {
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
                if (scrollToTable) {
                    const reducedMotion = window.matchMedia(
                        "(prefers-reduced-motion: reduce)",
                    ).matches;
                    container.scrollIntoView({
                        behavior: reducedMotion ? "auto" : "smooth",
                        block: "start",
                    });
                }
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
            loadPage(true);
        });

        firstButton.addEventListener("click", () => {
            state.page = 1;
            loadPage(true);
        });

        previousButton.addEventListener("click", () => {
            state.page = Math.max(1, state.page - 1);
            loadPage(true);
        });

        nextButton.addEventListener("click", () => {
            state.page = Math.min(state.pageCount, state.page + 1);
            loadPage(true);
        });

        lastButton.addEventListener("click", () => {
            state.page = state.pageCount;
            loadPage(true);
        });

        jumpInput.addEventListener("input", () => {
            jumpInput.setCustomValidity("");
        });

        jumpForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const requestedPage = Number(jumpInput.value);
            if (
                !Number.isInteger(requestedPage)
                || requestedPage < 1
                || requestedPage > state.pageCount
            ) {
                jumpInput.setCustomValidity(
                    `Enter a page from 1 to ${state.pageCount}.`,
                );
                jumpInput.reportValidity();
                return;
            }

            jumpInput.setCustomValidity("");
            jumpInput.value = "";
            state.page = requestedPage;
            loadPage(true);
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
