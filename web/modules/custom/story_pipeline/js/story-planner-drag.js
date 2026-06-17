/**
 * @file
 * Drag-and-drop reorder for Story planner planning queue.
 */
(function (Drupal, once) {
  'use strict';

  function getRows(table) {
    return Array.from(
      table.querySelectorAll('tbody tr.story-planner-draggable-row, tr.story-planner-draggable-row'),
    );
  }

  function updateOrder(table) {
    getRows(table).forEach((row, index) => {
      const weightInput = row.querySelector('.story-planner-weight-input');
      if (weightInput) {
        weightInput.value = String(index);
      }
      const badge = row.querySelector('.story-planner-priority');
      if (badge) {
        badge.textContent = '#' + (index + 1);
      }
    });
    table.classList.add('story-planner-order-changed');
  }

  Drupal.behaviors.storyPlannerDrag = {
    attach(context) {
      once('story-planner-drag', '.story-planner-order-table', context).forEach((table) => {
        let draggedRow = null;

        getRows(table).forEach((row) => {
          const grip = row.querySelector('.story-planner-drag-grip');
          if (!grip) {
            return;
          }

          grip.setAttribute('draggable', 'true');

          grip.addEventListener('dragstart', (event) => {
            draggedRow = row;
            row.classList.add('story-planner-row--dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', String(row.rowIndex));
          });

          grip.addEventListener('dragend', () => {
            row.classList.remove('story-planner-row--dragging');
            getRows(table).forEach((r) => r.classList.remove('story-planner-row--drop-target'));
            draggedRow = null;
            updateOrder(table);
          });

          row.addEventListener('dragover', (event) => {
            if (!draggedRow || draggedRow === row) {
              return;
            }
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            getRows(table).forEach((r) => r.classList.remove('story-planner-row--drop-target'));
            row.classList.add('story-planner-row--drop-target');

            const tbody = row.parentNode;
            const rect = row.getBoundingClientRect();
            const after = event.clientY > rect.top + rect.height / 2;
            if (after) {
              tbody.insertBefore(draggedRow, row.nextSibling);
            }
            else {
              tbody.insertBefore(draggedRow, row);
            }
            updateOrder(table);
          });

          row.addEventListener('drop', (event) => {
            event.preventDefault();
          });
        });

        updateOrder(table);
      });
    },
  };
})(Drupal, once);
