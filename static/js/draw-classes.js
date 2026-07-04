/** Draw-class dropdown HTML + color map for Correct tab */
export const CLASS_COLORS = {
  Wall: '#c80000', Window: '#ff00ff', Door: '#00a5ff', Room: '#00c800',
  Slab: '#646464', Roof: '#505050', Column: '#ffa500', Beam: '#8b4513',
  Stair: '#6464ff', Railing: '#b4b4b4', CurtainWall: '#c89696',
  Furniture: '#c8c800', Covering: '#d2b48c', LightFixture: '#ffffa5',
  ElectricAppliance: '#a5a5ff', FlowTerminal: '#a5ffa5', EnergyConversionDevice: '#ffc864',
};

export const DRAW_CLASS_SELECT_HTML = `
<optgroup label="── Spaces (IfcSpace) ──">
  <option value="Room" data-subtype="Living Room">Room — Living Room</option>
  <option value="Room" data-subtype="Dining Room">Room — Dining Room</option>
  <option value="Room" data-subtype="Drawing Room">Room — Drawing Room</option>
  <option value="Room" data-subtype="Bedroom">Room — Bedroom</option>
  <option value="Room" data-subtype="Master Bedroom">Room — Master Bedroom</option>
  <option value="Room" data-subtype="Kitchen">Room — Kitchen</option>
  <option value="Room" data-subtype="Bathroom">Room — Bathroom</option>
  <option value="Room" data-subtype="Toilet / WC">Room — Toilet / WC</option>
  <option value="Room" data-subtype="Balcony">Room — Balcony</option>
  <option value="Room" data-subtype="Entry / Foyer">Room — Entry / Foyer</option>
  <option value="Room" data-subtype="Corridor">Room — Corridor</option>
  <option value="Room" data-subtype="Utility / Wash">Room — Utility / Wash</option>
  <option value="Room" data-subtype="Store Room">Room — Store Room</option>
  <option value="Room" data-subtype="Study / Home Office">Room — Study / Home Office</option>
  <option value="Room" data-subtype="Puja Room">Room — Puja Room</option>
  <option value="Room" data-subtype="Parking / Garage">Room — Parking / Garage</option>
  <option value="Room" data-subtype="Servant Room">Room — Servant Room</option>
  <option value="Room" data-subtype="Gym">Room — Gym</option>
</optgroup>
<optgroup label="── Structure (IfcWall/Slab) ──">
  <option value="Wall" data-subtype="Exterior">Wall — Exterior</option>
  <option value="Wall" data-subtype="Interior">Wall — Interior</option>
  <option value="Wall" data-subtype="Partition">Wall — Partition</option>
  <option value="Slab">Slab</option>
  <option value="Roof">Roof</option>
  <option value="Column">Column</option>
  <option value="Beam">Beam</option>
  <option value="Railing">Railing</option>
  <option value="CurtainWall">Curtain Wall</option>
  <option value="Covering">Covering</option>
</optgroup>
<optgroup label="── Openings ──">
  <option value="Door" data-subtype="Single Swing">Door — Single Swing</option>
  <option value="Door" data-subtype="Double Swing">Door — Double Swing</option>
  <option value="Door" data-subtype="Sliding">Door — Sliding</option>
  <option value="Door" data-subtype="Folding">Door — Folding</option>
  <option value="Window" data-subtype="Sliding">Window — Sliding</option>
  <option value="Window" data-subtype="Casement">Window — Casement</option>
  <option value="Window" data-subtype="Fixed">Window — Fixed</option>
</optgroup>
<optgroup label="── Vertical ──">
  <option value="Stair" data-subtype="Straight">Stair — Straight</option>
  <option value="Stair" data-subtype="L-shaped">Stair — L-shaped</option>
  <option value="Stair" data-subtype="Spiral">Stair — Spiral</option>
</optgroup>
<optgroup label="── Furniture (IfcFurnishingElement) ──">
  <option value="Furniture" data-subtype="Sofa">Furniture — Sofa</option>
  <option value="Furniture" data-subtype="Bed">Furniture — Bed</option>
  <option value="Furniture" data-subtype="Wardrobe">Furniture — Wardrobe</option>
  <option value="Furniture" data-subtype="Dining Table">Furniture — Dining Table</option>
  <option value="Furniture" data-subtype="TV Unit">Furniture — TV Unit</option>
  <option value="Furniture" data-subtype="Cabinet">Furniture — Cabinet</option>
</optgroup>
<optgroup label="── MEP / Sanitary ──">
  <option value="FlowTerminal" data-subtype="WC / Toilet">Plumbing — WC / Toilet</option>
  <option value="FlowTerminal" data-subtype="Wash Basin">Plumbing — Wash Basin</option>
  <option value="FlowTerminal" data-subtype="Kitchen Sink">Plumbing — Kitchen Sink</option>
  <option value="FlowTerminal" data-subtype="Shower">Plumbing — Shower</option>
  <option value="LightFixture" data-subtype="Ceiling Light">Light — Ceiling</option>
  <option value="LightFixture" data-subtype="Recessed">Light — Recessed</option>
  <option value="ElectricAppliance" data-subtype="AC Unit">Appliance — AC Unit</option>
  <option value="ElectricAppliance" data-subtype="Refrigerator">Appliance — Refrigerator</option>
  <option value="ElectricAppliance" data-subtype="Stove / Hob">Appliance — Stove / Hob</option>
  <option value="EnergyConversionDevice">Energy Device</option>
</optgroup>`;

export function populateClassDropdowns(selectIds, yoloClasses) {
  const names = yoloClasses && yoloClasses.length
    ? yoloClasses
    : Object.keys(CLASS_COLORS);
  selectIds.forEach((id) => {
    const el = document.getElementById(id);
    if (!el || el.id === 'draw-class') return;
    const cur = el.value;
    el.innerHTML = id === 'filterClass' || id === 'bulkRelabelClass'
      ? '<option value="">All classes</option>'
      : '';
    if (id === 'bulkRelabelClass') el.innerHTML = '<option value="">Relabel to...</option>';
    names.forEach((n) => {
      const opt = document.createElement('option');
      opt.value = n;
      opt.textContent = n;
      el.appendChild(opt);
    });
    if (cur) el.value = cur;
  });
}

export function initDrawClassSelect() {
  const sel = document.getElementById('draw-class');
  if (sel) sel.innerHTML = DRAW_CLASS_SELECT_HTML;
}
