/**
 * @file
 * Defines JavaScript behaviors for the diff module.
 */

(function ($, Drupal, drupalSettings, once) {
  Drupal.behaviors.diffRevisions = {
    attach() {
      const rows = once('diff-revisions', 'table.diff-revisions tbody tr');
      const $rows = $(rows);
      if ($rows.length === 0) {
        return;
      }

      function updateDiffRadios() {
        let newTd = false;
        let oldTd = false;
        if (!$rows.length) {
          return true;
        }
        $rows.each(function () {
          const $row = $(this);
          const $inputs = $row.find('input[type="radio"]');
          const $oldRadio = $inputs.filter('[name="radios_left"]').eq(0);
          const $newRadio = $inputs.filter('[name="radios_right"]').eq(0);
          if (!$oldRadio.length || !$newRadio.length) {
            return true;
          }
          if ($oldRadio.prop('checked')) {
            oldTd = true;
            $oldRadio[0].classList.remove('js-hide');
            $newRadio[0].classList.add('js-hide');
          } else if ($newRadio.prop('checked')) {
            newTd = true;
            $oldRadio[0].classList.add('js-hide');
            $newRadio[0].classList.remove('js-hide');
          } else if (drupalSettings.diffRevisionRadios === 'linear') {
            if (newTd && oldTd) {
              $oldRadio[0].classList.remove('js-hide');
              $newRadio[0].classList.add('js-hide');
            } else if (newTd) {
              $oldRadio[0].classList.remove('js-hide');
              $newRadio[0].classList.remove('js-hide');
            } else {
              $newRadio[0].classList.remove('js-hide');
              $oldRadio[0].classList.add('js-hide');
            }
          } else {
            $oldRadio[0].classList.remove('js-hide');
            $newRadio[0].classList.remove('js-hide');
          }
        });
        return true;
      }

      if (drupalSettings.diffRevisionRadios) {
        $rows
          .find('input[name="radios_left"], input[name="radios_right"]')
          .click(updateDiffRadios);
        updateDiffRadios();
      }
    },
  };
})(jQuery, Drupal, drupalSettings, once);
