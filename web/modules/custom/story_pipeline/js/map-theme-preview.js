/**
 * Canvas preview using the same teardrop geometry as map-story/src/pin.js.
 */
(function (Drupal, drupalSettings, once) {
  function metrics(height) {
    const radius = height * 0.32;
    const centerY = -(height - radius);
    return { radius, centerY, holeRadius: radius * 0.46 };
  }

  function tracePin(ctx, height) {
    const { radius, centerY } = metrics(height);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(-radius * 0.2, centerY * 0.45, -radius, centerY);
    ctx.arc(0, centerY, radius, Math.PI, 0, false);
    ctx.quadraticCurveTo(radius * 0.2, centerY * 0.45, 0, 0);
    ctx.closePath();
  }

  function drawPin(ctx, x, y, token) {
    const height = 54;
    const { centerY, holeRadius } = metrics(height);
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = token.shadow || '#172B4D33';
    ctx.globalAlpha = 0.45;
    ctx.translate(2, 3);
    tracePin(ctx, height);
    ctx.fill();
    ctx.translate(-2, -3);
    ctx.globalAlpha = 1;
    ctx.fillStyle = token.fill || '#E60023';
    tracePin(ctx, height);
    ctx.fill();
    ctx.globalCompositeOperation = 'destination-out';
    ctx.beginPath();
    ctx.arc(0, centerY, holeRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = token.outline || '#FFFFFF';
    ctx.lineWidth = 2;
    tracePin(ctx, height);
    ctx.stroke();
    ctx.restore();
  }

  function selectedId() {
    const chosen = document.querySelector('input[name="map_theme"]:checked');
    return chosen ? chosen.value : 'documentary_relief_bold';
  }

  function themeDocument(id) {
    const theme = (drupalSettings.mapThemes || {})[id];
    if (!theme) {
      return null;
    }
    return theme.resolved || theme;
  }

  function selectedTheme() {
    return themeDocument(selectedId());
  }

  function setValue(name, value) {
    const field = document.querySelector('[name="' + name + '"]');
    if (!field || value == null) {
      return;
    }
    if (field.type === 'checkbox') {
      field.checked = value === true || value === '1' || value === 1;
    }
    else {
      field.value = value;
    }
    const picker = field.parentElement && field.parentElement.querySelector('input[data-map-color-for="' + name + '"]');
    if (picker && /^#[0-9A-Fa-f]{6}$/.test(String(value))) {
      picker.value = String(value).slice(0, 7);
    }
  }

  function applyTemplate(theme) {
    if (!theme) {
      return;
    }
    const tokens = theme.tokens || {};
    Object.keys(tokens).forEach(function (group) {
      const values = tokens[group];
      if (!values || typeof values !== 'object') {
        return;
      }
      Object.keys(values).forEach(function (key) {
        if (typeof values[key] === 'string') {
          setValue('customise[' + group + '][' + key + ']', values[key]);
        }
      });
    });
    const marker = theme.marker || {};
    const caps = theme.capabilities || {};
    setValue('customise[marker_shape]', marker.shape || caps.marker_shape || 'glow_dot');
    setValue('customise[hole_mode]', marker.hole === 'transparent' || !marker.hole ? 'transparent' : 'filled');
    setValue('customise[marker_height]', marker.height || 54);
    setValue('customise[outline_width]', marker.outline_width != null ? marker.outline_width : 2.25);
    setValue('customise[shadow_strength]', marker.shadow_strength != null ? marker.shadow_strength : 0.4);
    setValue('customise[pulse]', !!marker.pulse);
    setValue('customise[basemap_mode]', caps.basemap_mode || 'graded_relief');
    const label = theme.label || {};
    if (label.font_latin) setValue('customise[font_latin]', label.font_latin);
    if (label.font_devanagari) setValue('customise[font_devanagari]', label.font_devanagari);
  }

  function attachColorPickers(scope) {
    scope.querySelectorAll('input[data-map-token]').forEach(function (field) {
      if (!/^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$/.test(field.value.trim())) {
        return;
      }
      if (field.parentElement.querySelector('input[data-map-color-for]')) {
        return;
      }
      const picker = document.createElement('input');
      picker.type = 'color';
      picker.value = field.value.trim().slice(0, 7);
      picker.setAttribute('data-map-color-for', field.name);
      picker.addEventListener('input', function () {
        const alpha = field.value.trim().length === 9 ? field.value.trim().slice(7) : '';
        field.value = (picker.value + alpha).toUpperCase();
        const canvas = document.querySelector('.map-theme-preview');
        if (canvas) paint(canvas);
      });
      field.addEventListener('input', function () {
        if (/^#[0-9A-Fa-f]{6}/.test(field.value.trim())) {
          picker.value = field.value.trim().slice(0, 7);
        }
      });
      field.insertAdjacentElement('afterend', picker);
    });
  }

  function paint(canvas) {
    const theme = selectedTheme();
    if (!theme || !canvas.getContext) {
      return;
    }
    const tokens = JSON.parse(JSON.stringify(theme.tokens || {}));
    Object.keys(tokens).forEach(function (group) {
      Object.keys(tokens[group] || {}).forEach(function (key) {
        const field = document.querySelector('[name="customise[' + group + '][' + key + ']"]');
        if (field && field.value) {
          tokens[group][key] = field.value;
        }
      });
    });
    const shapeField = document.querySelector('[name="customise[marker_shape]"]');
    const background = tokens.background || {};
    const highlights = tokens.highlights || {};
    const labels = tokens.labels || {};
    const callout = tokens.callout || {};
    const banner = tokens.dateBanner || {};
    const marker = tokens.marker || {};
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = background.ocean || '#103E4A';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = background.land || '#8d7352';
    ctx.beginPath();
    ctx.moveTo(70, 40);
    ctx.lineTo(520, 70);
    ctx.lineTo(560, 250);
    ctx.lineTo(90, 280);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = background.contextBorder || '#e6d7a8';
    ctx.stroke();
    ctx.fillStyle = highlights.country || '#A32320';
    ctx.globalAlpha = 0.55;
    ctx.fillRect(120, 90, 280, 120);
    ctx.globalAlpha = 0.8;
    ctx.fillStyle = highlights.primaryRegion || '#D4B300';
    ctx.fillRect(180, 120, 90, 60);
    ctx.globalAlpha = 1;
    const shape = (shapeField && shapeField.value) || (theme.marker && theme.marker.shape) || 'glow_dot';
    if (shape === 'pin') {
      drawPin(ctx, 250, 210, marker);
    }
    else {
      ctx.fillStyle = marker.fill || '#FFF400';
      ctx.beginPath();
      ctx.arc(250, 170, 8, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = labels.text || '#FFFDF5';
    ctx.font = '28px sans-serif';
    ctx.fillText('गांधीनगर', 270, 150);
    ctx.font = '16px sans-serif';
    ctx.fillStyle = labels.secondaryText || labels.text || '#FFFDF5';
    ctx.fillText('Gujarat', 270, 176);
    ctx.fillStyle = callout.background || '#FFFFFFF2';
    ctx.fillRect(40, 250, 150, 48);
    ctx.strokeStyle = callout.border || '#D4DCE4';
    ctx.strokeRect(40, 250, 150, 48);
    ctx.fillStyle = callout.text || '#172B4D';
    ctx.fillText('Gandhinagar', 52, 280);
    ctx.strokeStyle = callout.arrow || '#E60023';
    ctx.beginPath();
    ctx.moveTo(190, 274);
    ctx.lineTo(240, 200);
    ctx.stroke();
    ctx.fillStyle = banner.background || '#172B4D';
    ctx.fillRect(0, 0, w, 36);
    ctx.fillStyle = banner.text || '#FFFFFF';
    ctx.font = '20px sans-serif';
    ctx.fillText('2026', 16, 25);
  }

  Drupal.behaviors.mapThemePreview = {
    attach(context) {
      once('map-theme-preview', '.map-theme-preview', context).forEach(function (canvas) {
        const form = canvas.closest('form') || document;
        attachColorPickers(form);
        const draw = function () { paint(canvas); };
        applyTemplate(selectedTheme());
        draw();
        form.querySelectorAll('input[name="map_theme"]').forEach(function (input) {
          input.addEventListener('change', function () {
            applyTemplate(themeDocument(input.value));
            draw();
          });
        });
        form.querySelectorAll('.map-theme-reset').forEach(function (button) {
          button.addEventListener('click', function (event) {
            event.preventDefault();
            applyTemplate(selectedTheme());
            draw();
          });
        });
      });
    }
  };
})(Drupal, drupalSettings, once);
