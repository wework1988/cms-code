(function (Drupal, once) {
  function debounce(fn, wait) {
    let timer;
    return function () {
      const args = arguments;
      const context = this;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        fn.apply(context, args);
      }, wait);
    };
  }

  function draw(box, geometry) {
    if (!box || !window.maplibregl || !geometry) {
      return;
    }
    if (box._map) {
      box._map.remove();
      box._map = null;
    }
    const map = new window.maplibregl.Map({
      container: box,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors'
          }
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
      },
      attributionControl: true
    });
    box._map = map;
    map.on('load', function () {
      map.addSource('place', { type: 'geojson', data: geometry });
      if (geometry.type === 'Point') {
        map.addLayer({
          id: 'place-point',
          type: 'circle',
          source: 'place',
          paint: { 'circle-radius': 7, 'circle-color': '#E6D545', 'circle-stroke-width': 2, 'circle-stroke-color': '#E52B32' }
        });
        map.flyTo({ center: geometry.coordinates, zoom: 8 });
      }
      else {
        map.addLayer({
          id: 'place-fill',
          type: 'fill',
          source: 'place',
          paint: { 'fill-color': '#E52B32', 'fill-opacity': 0.25 }
        });
        map.addLayer({
          id: 'place-line',
          type: 'line',
          source: 'place',
          paint: { 'line-color': '#E52B32', 'line-width': 2 }
        });
        const bounds = new window.maplibregl.LngLatBounds();
        const visit = function (coords) {
          if (typeof coords[0] === 'number') {
            bounds.extend(coords);
            return;
          }
          coords.forEach(visit);
        };
        visit(geometry.coordinates);
        map.fitBounds(bounds, { padding: 32, maxZoom: 8 });
      }
    });
  }

  function loadPreview(id, box, hierarchy, url) {
    if (!id) {
      return;
    }
    window.fetch(url + '?id=' + encodeURIComponent(id), { headers: { Accept: 'application/json' } })
      .then(function (response) { return response.json(); })
      .then(function (place) {
        if (!place || place.error) {
          if (hierarchy) {
            hierarchy.textContent = place && place.error ? place.error : 'That catalogue id could not be previewed.';
          }
          return;
        }
        if (hierarchy) {
          hierarchy.textContent = [
            place.name,
            place.alternate_name,
            place.country_name || place.country_code,
            place.state_name,
            place.level_label || place.level,
            place.feature_type,
            place.representation,
            place.source_namespace
          ].filter(Boolean).join(' · ');
        }
        const root = box ? box.closest('[data-location-request]') : null;
        if (root) {
          const stateInput = root.querySelector('[data-location-state]');
          const countryInput = root.querySelector('[data-location-country]');
          if (stateInput && place.state_name) {
            stateInput.value = place.state_name;
          }
          if (countryInput && place.country_code) {
            countryInput.value = place.country_code;
          }
        }
        draw(box, place.geometry);
      })
      .catch(function () {
        if (hierarchy) {
          hierarchy.textContent = 'That catalogue id could not be previewed.';
        }
      });
  }

  Drupal.behaviors.locationResolution = {
    attach(context) {
      once('location-search', '[data-location-search]', context).forEach(function (input) {
        const root = input.closest('[data-location-request]');
        if (!root) {
          return;
        }
        const select = root.querySelector('[data-location-results]');
        const hierarchy = root.querySelector('[data-location-hierarchy]');
        const box = root.querySelector('[data-location-map]');
        const stateInput = root.querySelector('[data-location-state]');
        const countryInput = root.querySelector('[data-location-country]');
        const levelInput = root.querySelector('[data-location-level]');
        let requestToken = 0;
        const run = debounce(function () {
          const token = ++requestToken;
          const params = new URLSearchParams({
            q: input.value.trim(),
            limit: '8'
          });
          if (stateInput && stateInput.value.trim()) {
            params.set('state', stateInput.value.trim());
          }
          if (countryInput && countryInput.value.trim()) {
            params.set('country', countryInput.value.trim());
          }
          if (levelInput && levelInput.value.trim()) {
            params.set('level', levelInput.value.trim());
          }
          const selected = select.selectedOptions[0];
          const selectedValue = selected ? selected.value : '';
          const selectedText = selected ? selected.textContent : '';
          window.fetch(input.dataset.searchUrl + '?' + params.toString(), { headers: { Accept: 'application/json' } })
            .then(function (response) { return response.json(); })
            .then(function (payload) {
              if (token !== requestToken) {
                return;
              }
              select.replaceChildren();
              const empty = document.createElement('option');
              empty.value = '';
              empty.textContent = 'Choose a catalogue place';
              select.appendChild(empty);
              (payload.results || []).forEach(function (row) {
                const option = document.createElement('option');
                option.value = row.id;
                option.textContent = [
                  row.name,
                  row.alternate_name,
                  row.country_name || row.country_code,
                  row.state_name,
                  row.level_label || row.level,
                  row.feature_type,
                  row.representation,
                  row.source_namespace
                ].filter(Boolean).join(' · ');
                select.appendChild(option);
              });
              if (selectedValue && ![...select.options].some(function (option) { return option.value === selectedValue; })) {
                const kept = document.createElement('option');
                kept.value = selectedValue;
                kept.textContent = selectedText;
                select.appendChild(kept);
              }
              if (selectedValue) {
                select.value = selectedValue;
              }
            });
        }, 300);
        input.addEventListener('input', run);
        if (stateInput) {
          stateInput.addEventListener('input', run);
        }
        if (countryInput) {
          countryInput.addEventListener('change', run);
          countryInput.addEventListener('input', run);
        }
        if (levelInput) {
          levelInput.addEventListener('change', run);
        }
        select.addEventListener('change', function () {
          loadPreview(select.value, box, hierarchy, input.dataset.previewUrl);
        });
      });

      once('custom-point-map', '[data-custom-map]', context).forEach(function (box) {
        if (!window.maplibregl) {
          return;
        }
        const lat = document.querySelector('[name="' + box.dataset.latName + '"]');
        const lon = document.querySelector('[name="' + box.dataset.lonName + '"]');
        const map = new window.maplibregl.Map({
          container: box,
          style: {
            version: 8,
            sources: {
              osm: {
                type: 'raster',
                tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                tileSize: 256,
                attribution: '© OpenStreetMap contributors'
              }
            },
            layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
          },
          center: [78, 22],
          zoom: 3.5
        });
        let marker = null;
        map.on('click', function (event) {
          if (lat) {
            lat.value = event.lngLat.lat.toFixed(5);
          }
          if (lon) {
            lon.value = event.lngLat.lng.toFixed(5);
          }
          if (marker) {
            marker.setLngLat(event.lngLat);
          }
          else {
            marker = new window.maplibregl.Marker({ color: '#E52B32' }).setLngLat(event.lngLat).addTo(map);
          }
        });
      });
    }
  };
})(Drupal, once);
