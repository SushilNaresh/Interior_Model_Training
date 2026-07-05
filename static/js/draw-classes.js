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
  <option value="Room" data-subtype="Kids Bedroom">Room — Kids Bedroom</option>
  <option value="Room" data-subtype="Guest Bedroom">Room — Guest Bedroom</option>
  <option value="Room" data-subtype="Kitchen">Room — Kitchen</option>
  <option value="Room" data-subtype="Kitchenette">Room — Kitchenette</option>
  <option value="Room" data-subtype="Bathroom">Room — Bathroom</option>
  <option value="Room" data-subtype="Toilet / WC">Room — Toilet / WC</option>
  <option value="Room" data-subtype="Powder Room">Room — Powder Room</option>
  <option value="Room" data-subtype="Balcony">Room — Balcony</option>
  <option value="Room" data-subtype="Terrace">Room — Terrace</option>
  <option value="Room" data-subtype="Entry / Foyer">Room — Entry / Foyer</option>
  <option value="Room" data-subtype="Corridor">Room — Corridor</option>
  <option value="Room" data-subtype="Lobby">Room — Lobby</option>
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
  <option value="Wall" data-subtype="Retaining">Wall — Retaining</option>
  <option value="Wall" data-subtype="Curtain">Wall — Curtain</option>
  <option value="Slab" data-subtype="Floor Slab">Slab — Floor Slab</option>
  <option value="Slab" data-subtype="Roof Slab">Slab — Roof Slab</option>
  <option value="Slab" data-subtype="Stair Landing">Slab — Stair Landing</option>
  <option value="Slab" data-subtype="Ramp">Slab — Ramp</option>
  <option value="Roof">Roof</option>
  <option value="Column" data-subtype="RCC">Column — RCC</option>
  <option value="Column" data-subtype="Steel">Column — Steel</option>
  <option value="Column" data-subtype="Timber">Column — Timber</option>
  <option value="Column" data-subtype="Composite">Column — Composite</option>
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
  <option value="Door" data-subtype="Revolving">Door — Revolving</option>
  <option value="Door" data-subtype="Flush">Door — Flush</option>
  <option value="Door" data-subtype="Arched">Door — Arched</option>
  <option value="Door" data-subtype="Pivot">Door — Pivot</option>
  <option value="Window" data-subtype="Sliding">Window — Sliding</option>
  <option value="Window" data-subtype="Casement">Window — Casement</option>
  <option value="Window" data-subtype="Fixed">Window — Fixed</option>
  <option value="Window" data-subtype="Awning">Window — Awning</option>
  <option value="Window" data-subtype="Louvered">Window — Louvered</option>
  <option value="Window" data-subtype="Bay">Window — Bay</option>
  <option value="Window" data-subtype="Skylight">Window — Skylight</option>
</optgroup>
<optgroup label="── Vertical ──">
  <option value="Stair" data-subtype="Straight">Stair — Straight</option>
  <option value="Stair" data-subtype="L-shaped">Stair — L-shaped</option>
  <option value="Stair" data-subtype="U-shaped">Stair — U-shaped</option>
  <option value="Stair" data-subtype="Spiral">Stair — Spiral</option>
  <option value="Stair" data-subtype="Winder">Stair — Winder</option>
</optgroup>
<optgroup label="── Furniture (IfcFurnishingElement) ──">
  <option value="Furniture" data-subtype="Sofa">Furniture — Sofa</option>
  <option value="Furniture" data-subtype="Sofa Set">Furniture — Sofa Set</option>
  <option value="Furniture" data-subtype="L-Shaped Sofa">Furniture — L-Shaped Sofa</option>
  <option value="Furniture" data-subtype="Recliner">Furniture — Recliner</option>
  <option value="Furniture" data-subtype="Bed">Furniture — Bed</option>
  <option value="Furniture" data-subtype="Wardrobe">Furniture — Wardrobe</option>
  <option value="Furniture" data-subtype="Dining Table">Furniture — Dining Table</option>
  <option value="Furniture" data-subtype="Dining Chair">Furniture — Dining Chair</option>
  <option value="Furniture" data-subtype="Chair">Furniture — Chair</option>
  <option value="Furniture" data-subtype="Accent Chair">Furniture — Accent Chair</option>
  <option value="Furniture" data-subtype="TV Unit">Furniture — TV Unit</option>
  <option value="Furniture" data-subtype="Study Table">Furniture — Study Table</option>
  <option value="Furniture" data-subtype="Bookshelf">Furniture — Bookshelf</option>
  <option value="Furniture" data-subtype="Cabinet">Furniture — Cabinet</option>
  <option value="Furniture" data-subtype="Coffee Table">Furniture — Coffee Table</option>
  <option value="Furniture" data-subtype="Centre Table">Furniture — Centre Table</option>
  <option value="Furniture" data-subtype="Side Table">Furniture — Side Table</option>
  <option value="Furniture" data-subtype="Dressing Table">Furniture — Dressing Table</option>
  <option value="Furniture" data-subtype="Bar Stool">Furniture — Bar Stool</option>
  <option value="Furniture" data-subtype="Bean Bag">Furniture — Bean Bag</option>
  <option value="Furniture" data-subtype="Shoe Rack">Furniture — Shoe Rack</option>
  <option value="Furniture" data-subtype="Pooja Mandir">Furniture — Pooja Mandir</option>
</optgroup>
<optgroup label="── Sanitary / Plumbing ──">
  <option value="FlowTerminal" data-subtype="WC / Toilet">Plumbing — WC / Toilet</option>
  <option value="FlowTerminal" data-subtype="Wash Basin">Plumbing — Wash Basin</option>
  <option value="FlowTerminal" data-subtype="Kitchen Sink">Plumbing — Kitchen Sink</option>
  <option value="FlowTerminal" data-subtype="Shower">Plumbing — Shower</option>
  <option value="FlowTerminal" data-subtype="Bathtub">Plumbing — Bathtub</option>
  <option value="FlowTerminal" data-subtype="Urinal">Plumbing — Urinal</option>
</optgroup>
<optgroup label="── Appliances (IfcElectricAppliance) ──">
  <option value="ElectricAppliance" data-subtype="Refrigerator">Appliance — Refrigerator</option>
  <option value="ElectricAppliance" data-subtype="Single Door Fridge">Appliance — Single Door Fridge</option>
  <option value="ElectricAppliance" data-subtype="Double Door Fridge">Appliance — Double Door Fridge</option>
  <option value="ElectricAppliance" data-subtype="Side-by-Side Fridge">Appliance — Side-by-Side Fridge</option>
  <option value="ElectricAppliance" data-subtype="Washing Machine">Appliance — Washing Machine</option>
  <option value="ElectricAppliance" data-subtype="Front Load Washer">Appliance — Front Load Washer</option>
  <option value="ElectricAppliance" data-subtype="Top Load Washer">Appliance — Top Load Washer</option>
  <option value="ElectricAppliance" data-subtype="Dishwasher">Appliance — Dishwasher</option>
  <option value="ElectricAppliance" data-subtype="Microwave">Appliance — Microwave</option>
  <option value="ElectricAppliance" data-subtype="OTG">Appliance — OTG</option>
  <option value="ElectricAppliance" data-subtype="Convection Microwave">Appliance — Convection Microwave</option>
  <option value="ElectricAppliance" data-subtype="Gas Stove">Appliance — Gas Stove</option>
  <option value="ElectricAppliance" data-subtype="Induction Cooktop">Appliance — Induction Cooktop</option>
  <option value="ElectricAppliance" data-subtype="Chimney / Hood">Appliance — Chimney / Hood</option>
  <option value="ElectricAppliance" data-subtype="Cooking Range">Appliance — Cooking Range</option>
  <option value="ElectricAppliance" data-subtype="Split AC">Appliance — Split AC</option>
  <option value="ElectricAppliance" data-subtype="Window AC">Appliance — Window AC</option>
  <option value="ElectricAppliance" data-subtype="Cassette AC">Appliance — Cassette AC</option>
  <option value="ElectricAppliance" data-subtype="Portable AC">Appliance — Portable AC</option>
  <option value="ElectricAppliance" data-subtype="Ceiling Fan">Appliance — Ceiling Fan</option>
  <option value="ElectricAppliance" data-subtype="Exhaust Fan">Appliance — Exhaust Fan</option>
  <option value="ElectricAppliance" data-subtype="Pedestal Fan">Appliance — Pedestal Fan</option>
  <option value="ElectricAppliance" data-subtype="Water Heater / Geyser">Appliance — Water Heater / Geyser</option>
  <option value="ElectricAppliance" data-subtype="Water Purifier / RO">Appliance — Water Purifier / RO</option>
  <option value="ElectricAppliance" data-subtype="Television / TV">Appliance — Television / TV</option>
  <option value="ElectricAppliance" data-subtype="Air Purifier">Appliance — Air Purifier</option>
  <option value="ElectricAppliance" data-subtype="Mixer Grinder">Appliance — Mixer Grinder</option>
  <option value="EnergyConversionDevice">Energy Device</option>
</optgroup>
<optgroup label="── Lighting (IfcLightFixture) ──">
  <option value="LightFixture" data-subtype="Ceiling Light">Light — Ceiling Light</option>
  <option value="LightFixture" data-subtype="Pendant">Light — Pendant</option>
  <option value="LightFixture" data-subtype="Recessed">Light — Recessed</option>
  <option value="LightFixture" data-subtype="Wall Sconce">Light — Wall Sconce</option>
  <option value="LightFixture" data-subtype="Floor Lamp">Light — Floor Lamp</option>
  <option value="LightFixture" data-subtype="Track Light">Light — Track Light</option>
</optgroup>`;

export function populateClassDropdowns(selectIds, yoloClasses) {
  selectIds.forEach((id) => {
    const el = document.getElementById(id);
    if (!el || el.id === 'draw-class') return;
    const cur = el.value;
    if (id === 'filterClass') {
      el.innerHTML = '<option value="">All classes</option>' + DRAW_CLASS_SELECT_HTML;
    } else if (id === 'bulkRelabelClass') {
      el.innerHTML = '<option value="">Relabel to...</option>' + DRAW_CLASS_SELECT_HTML;
    } else {
      el.innerHTML = '';
      Object.keys(CLASS_COLORS).forEach((n) => {
        const opt = document.createElement('option');
        opt.value = n; opt.textContent = n;
        el.appendChild(opt);
      });
    }
    if (cur) el.value = cur;
  });
}

export function initDrawClassSelect() {
  const sel = document.getElementById('draw-class');
  if (sel) sel.innerHTML = DRAW_CLASS_SELECT_HTML;
}
