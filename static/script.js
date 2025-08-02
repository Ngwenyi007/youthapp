// static/forms.js (or similar)

document.addEventListener('DOMContentLoaded', function() {
    const levelSelect = document.getElementById('level-select'); // Assuming you have a select for church level
    const rankSelect = document.getElementById('rank-select');   // Assuming you have a select for rank

    function updateRanks() {
        const level = levelSelect.value;
        let ranks = [];

        // Define ranks based on the selected church level
        // For 'member' level (no specific church, just a member)
        if (level === 'member') {
            ranks = ['Member'];
        }
        // For 'local_church' or 'parish' level leaders
        else if (level === 'local_church' || level === 'parish') {
            ranks = ['Chairman', 'Secretary', 'Treasurer', 'Matron', 'Patron', 'Organising Secretary'];
        }
        // For 'denary' or 'diocese' level leaders
        else if (level === 'denary' || level === 'diocese') {
            ranks = ['Chairman', 'Secretary', 'Treasurer', 'Matron', 'Patron', 'Chaplain', 'Organising Secretary'];
        }
        // Default or for an 'all' type if applicable
        else {
            ranks = ['Member']; // Fallback
        }

        // Populate the rank select dropdown
        rankSelect.innerHTML = ''; // Clear existing options
        ranks.forEach(rank => {
            const option = document.createElement('option');
            option.value = rank;
            option.textContent = rank;
            rankSelect.appendChild(option);
        });
    }

    // Attach event listener if the elements exist on the page
    if (levelSelect && rankSelect) {
        levelSelect.addEventListener('change', updateRanks);
        // Call once on page load to set initial ranks
        updateRanks();
    }
});
