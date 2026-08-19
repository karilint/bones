(function () {
    "use strict";

    const styles = {
        track: {color: "#1565c0", weight: 4, opacity: 0.9},
        parent_track: {color: "#607d8b", weight: 3, opacity: 0.6, dashArray: "7 5"},
        summary_line: {color: "#546e7a", weight: 2, opacity: 0.75},
        start: {color: "#1b5e20", fillColor: "#43a047"},
        turn: {color: "#e65100", fillColor: "#fb8c00"},
        end: {color: "#b71c1c", fillColor: "#e53935"},
        occurrence: {color: "#283593", fillColor: "#5c6bc0"},
        selected_occurrence: {color: "#4a148c", fillColor: "#ab47bc", radius: 9}
    };
    const trackColors = ["#1565c0", "#c62828", "#2e7d32", "#6a1b9a", "#ef6c00"];

    function popupContent(properties) {
        const wrapper = document.createElement("div");
        const strong = document.createElement("strong");
        strong.textContent = properties.label || "Location";
        wrapper.appendChild(strong);
        if (properties.transect_uid) {
            const details = document.createElement("div");
            const values = [
                properties.template_name,
                "UID " + properties.transect_uid,
                properties.walked
            ].filter(Boolean);
            details.textContent = values.join(" · ");
            wrapper.appendChild(details);
        }
        if (properties.url) {
            wrapper.appendChild(document.createElement("br"));
            const link = document.createElement("a");
            link.href = properties.url;
            link.textContent = "Open record";
            wrapper.appendChild(link);
        }
        return wrapper;
    }

    function bindHoverPopup(featureLayer) {
        let closeTimer;
        function cancelClose() {
            if (closeTimer) window.clearTimeout(closeTimer);
        }
        function scheduleClose() {
            cancelClose();
            closeTimer = window.setTimeout(function () {
                featureLayer.closePopup();
            }, 400);
        }
        featureLayer.on("mouseover focus", function () {
            cancelClose();
            featureLayer.openPopup();
        });
        featureLayer.on("mouseout blur", scheduleClose);
        featureLayer.on("popupopen", function (event) {
            const element = event.popup.getElement();
            if (!element || element.dataset.bonesHoverBound) return;
            element.dataset.bonesHoverBound = "true";
            element.addEventListener("mouseenter", cancelClose);
            element.addEventListener("mouseleave", scheduleClose);
        });
        featureLayer.on("add", function () {
            const element = featureLayer.getElement && featureLayer.getElement();
            if (element) {
                element.setAttribute("tabindex", "0");
                element.setAttribute("role", "button");
            }
        });
    }
    function featureStyle(feature) {
        const properties = feature.properties || {};
        const base = styles[properties.kind] || styles.track;
        if (properties.kind !== "track" && properties.kind !== "parent_track") return base;
        const index = Number(properties.track_index) || 0;
        return Object.assign({}, base, {
            color: trackColors[index % trackColors.length],
            dashArray: properties.kind === "parent_track" || index > 0 ? "7 5" : null
        });
    }

    function escapeHtml(value) {
        const element = document.createElement("span");
        element.textContent = value;
        return element.innerHTML;
    }

    function updateStatus(mapElement, message, error) {
        const status = mapElement.previousElementSibling;
        if (!status || !status.classList.contains("bones-map-status")) return;
        status.textContent = message;
        status.classList.toggle("w3-pale-red", Boolean(error));
        status.classList.toggle("w3-pale-blue", !error);
        status.hidden = !message;
    }

    let leafletPromise;

    function loadLeaflet(mapElement) {
        if (window.L) return Promise.resolve(window.L);
        if (leafletPromise) return leafletPromise;

        const cssUrl = mapElement.dataset.leafletCssUrl;
        if (cssUrl && !document.querySelector('link[data-bones-leaflet]')) {
            const stylesheet = document.createElement("link");
            stylesheet.rel = "stylesheet";
            stylesheet.href = cssUrl;
            stylesheet.dataset.bonesLeaflet = "true";
            document.head.appendChild(stylesheet);
        }

        leafletPromise = new Promise(function (resolve, reject) {
            const script = document.createElement("script");
            script.src = mapElement.dataset.leafletJsUrl;
            script.dataset.bonesLeaflet = "true";
            script.onload = function () {
                if (window.L) resolve(window.L);
                else reject(new Error("Leaflet did not initialize"));
            };
            script.onerror = function () {
                reject(new Error("Leaflet could not be loaded"));
            };
            document.body.appendChild(script);
        });
        return leafletPromise;
    }

    async function initialize(mapElement) {
        if (mapElement.dataset.mapState || mapElement.offsetParent === null) return;
        mapElement.dataset.mapState = "loading";
        updateStatus(mapElement, "Loading map data\u2026", false);

        try {
            await loadLeaflet(mapElement);
            const response = await fetch(mapElement.dataset.mapUrl, {
                credentials: "same-origin",
                headers: {"Accept": "application/geo+json, application/json"}
            });
            if (!response.ok) throw new Error("HTTP " + response.status);
            const geojson = await response.json();

            const map = window.L.map(mapElement, {scrollWheelZoom: false});
            const maxZoom = Number(mapElement.dataset.tileMaxZoom) || 17;
            window.L.tileLayer(mapElement.dataset.tileUrl, {
                attribution: mapElement.dataset.tileAttribution,
                maxNativeZoom: maxZoom,
                maxZoom: maxZoom + 2
            }).addTo(map);
            window.L.control.scale({
                position: "bottomleft",
                metric: true,
                imperial: false,
                maxWidth: 160
            }).addTo(map);

            const layer = window.L.geoJSON(geojson, {
                style: featureStyle,
                pointToLayer: function (feature, latlng) {
                    const options = Object.assign(
                        {radius: 7, weight: 2, opacity: 1, fillOpacity: 0.85},
                        featureStyle(feature)
                    );
                    return window.L.circleMarker(latlng, options);
                },
                onEachFeature: function (feature, featureLayer) {
                    featureLayer.bindPopup(
                        popupContent(feature.properties || {}),
                        {autoPan: false}
                    );
                    bindHoverPopup(featureLayer);
                }
            }).addTo(map);

            const deviceLayers = {};
            layer.eachLayer(function (featureLayer) {
                const feature = featureLayer.feature || {};
                const properties = feature.properties || {};
                if (feature.geometry && feature.geometry.type === "LineString" && properties.device) {
                    deviceLayers[escapeHtml(properties.device)] = featureLayer;
                }
            });
            if (Object.keys(deviceLayers).length > 1) {
                window.L.control.layers(null, deviceLayers, {collapsed: false}).addTo(map);
            }

            if (layer.getLayers().length) {
                const bounds = layer.getBounds();
                if (bounds.isValid()) {
                    map.fitBounds(bounds, {padding: [24, 24], maxZoom: 16});
                }
                updateStatus(mapElement, "", false);
            } else {
                map.setView([0, 0], 2);
                updateStatus(mapElement, "No valid coordinates are available for this record.", false);
            }
            mapElement._bonesMap = map;
            mapElement.dataset.mapState = "ready";
            window.setTimeout(function () { map.invalidateSize(); }, 0);
        } catch (error) {
            mapElement.dataset.mapState = "error";
            updateStatus(mapElement, "Map data could not be loaded. Please try again.", true);
        }
    }

    function initializeVisibleMaps() {
        document.querySelectorAll("[data-bones-map]").forEach(initialize);
    }

    window.initializeBonesMaps = initializeVisibleMaps;
    window.addEventListener("bones:tab-opened", function () {
        window.setTimeout(initializeVisibleMaps, 0);
    });

    document.addEventListener("DOMContentLoaded", function () {
        initializeVisibleMaps();
    });
}());
