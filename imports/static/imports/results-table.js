"use strict";

(() => {
    const dataElement = document.getElementById("analysis-data");
    if (!dataElement) {
        return;
    }

    const tableData = JSON.parse(dataElement.textContent);
    const collator = new Intl.Collator(undefined, {
        numeric: true,
        sensitivity: "base",
    });

    const searchableText = (row) => Object.values(row)
        .flatMap((value) => Array.isArray(value) ? value : [value])
        .join(" ")
        .toLocaleLowerCase();

    const comparableValue = (value) => {
        if (Array.isArray(value)) {
            return value.join(" ");
        }
        return value ?? "";
    };

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

    document.querySelectorAll("[data-table-key]").forEach((container) => {
        const tableKey = container.dataset.tableKey;
        const rows = tableData[tableKey] ?? [];
        const indexedRows = rows.map((row, sourceIndex) => ({
            row,
            sourceIndex,
            searchText: searchableText(row),
        }));

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
            page: 1,
            pageSize: Number(pageSizeSelect.value),
            query: "",
            sortDirection: "ascending",
            sortKey: null,
            sortType: "text",
            visibleRows: indexedRows,
        };

        const updateSortIndicators = () => {
            sortButtons.forEach((button) => {
                const active = button.dataset.sortKey === state.sortKey;
                const header = button.closest("th");
                const indicator = button.querySelector("[data-sort-indicator]");

                header.setAttribute(
                    "aria-sort",
                    active ? state.sortDirection : "none",
                );
                indicator.textContent = active
                    ? (state.sortDirection === "ascending" ? " ▲" : " ▼")
                    : "";
            });
        };

        const compareRows = (left, right) => {
            const leftValue = comparableValue(left.row[state.sortKey]);
            const rightValue = comparableValue(right.row[state.sortKey]);
            let comparison;

            if (state.sortType === "number") {
                comparison = Number(leftValue) - Number(rightValue);
            } else {
                comparison = collator.compare(String(leftValue), String(rightValue));
            }

            if (comparison !== 0 && state.sortDirection === "descending") {
                comparison *= -1;
            }
            return comparison || left.sourceIndex - right.sourceIndex;
        };

        const render = () => {
            const pageCount = Math.max(
                1,
                Math.ceil(state.visibleRows.length / state.pageSize),
            );

            state.page = Math.min(state.page, pageCount);
            const firstIndex = (state.page - 1) * state.pageSize;
            const pageRows = state.visibleRows.slice(
                firstIndex,
                firstIndex + state.pageSize,
            );
            const fragment = document.createDocumentFragment();

            pageRows.forEach(({ row }) => {
                const tableRow = document.createElement("tr");
                sortButtons.forEach((button) => {
                    const cell = document.createElement("td");
                    renderCell(cell, row[button.dataset.sortKey]);
                    tableRow.append(cell);
                });
                fragment.append(tableRow);
            });

            body.replaceChildren(fragment);

            const hasMatches = state.visibleRows.length > 0;
            tableWrap.hidden = !hasMatches;
            pagination.hidden = !hasMatches;
            emptyMessage.hidden = hasMatches;
            emptyMessage.textContent = rows.length === 0
                ? emptyMessage.dataset.emptyMessage
                : "No rows match the current search.";

            if (hasMatches) {
                const firstShown = firstIndex + 1;
                const lastShown = Math.min(
                    firstIndex + state.pageSize,
                    state.visibleRows.length,
                );
                summary.textContent = state.query
                    ? `${firstShown}–${lastShown} of ${state.visibleRows.length} matching rows (${rows.length} total)`
                    : `${firstShown}–${lastShown} of ${rows.length} rows`;
                pageLabel.textContent = `Page ${state.page} of ${pageCount}`;
            } else {
                summary.textContent = rows.length === 0
                    ? "0 rows"
                    : `0 matching rows (${rows.length} total)`;
                pageLabel.textContent = "Page 0 of 0";
            }

            previousButton.disabled = state.page <= 1;
            nextButton.disabled = state.page >= pageCount;
            updateSortIndicators();
        };

        const rebuildVisibleRows = () => {
            const matchingRows = state.query
                ? indexedRows.filter((entry) => entry.searchText.includes(state.query))
                : indexedRows;
            state.visibleRows = state.sortKey
                ? [...matchingRows].sort(compareRows)
                : matchingRows;
            render();
        };

        let searchTimer;
        searchInput.addEventListener("input", () => {
            window.clearTimeout(searchTimer);
            searchTimer = window.setTimeout(() => {
                state.query = searchInput.value.trim().toLocaleLowerCase();
                state.page = 1;
                rebuildVisibleRows();
            }, 150);
        });

        pageSizeSelect.addEventListener("change", () => {
            state.pageSize = Number(pageSizeSelect.value);
            state.page = 1;
            render();
        });

        previousButton.addEventListener("click", () => {
            state.page = Math.max(1, state.page - 1);
            render();
        });

        nextButton.addEventListener("click", () => {
            state.page += 1;
            render();
        });

        sortButtons.forEach((button) => {
            button.addEventListener("click", () => {
                if (state.sortKey === button.dataset.sortKey) {
                    state.sortDirection = state.sortDirection === "ascending"
                        ? "descending"
                        : "ascending";
                } else {
                    state.sortKey = button.dataset.sortKey;
                    state.sortType = button.dataset.sortType ?? "text";
                    state.sortDirection = "ascending";
                }
                state.page = 1;
                rebuildVisibleRows();
            });
        });

        const hasRows = rows.length > 0;
        searchInput.disabled = !hasRows;
        pageSizeSelect.disabled = !hasRows;
        container.dataset.enhanced = "true";
        rebuildVisibleRows();
    });
})();
