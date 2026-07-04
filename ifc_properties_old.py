# logic/ifc_properties.py
# IFC Property Sets (Psets) schema for floor plan elements.
# Covers: Rooms, Doors, Windows, Furniture, Sanitary, Appliances.
# UPDATED: All properties now have complete default values for consistent BIM data

import re
import ifcopenshell

IFC_SCHEMA = {
    "Room": {
        "ifc_class": "IfcSpace",
        # IFC4: IfcSpace.PredefinedType
        "predefined_types": ["SPACE", "PARKING", "GFA", "INTERNAL", "EXTERNAL"],
        # Subtypes = IfcSpace.LongName mapped to Uniclass 2015 SL codes
        "subtypes": [
            "Living Room (SL_25_10_30)",
            "Dining Room (SL_25_10_47)",
            "Drawing Room (SL_25_10_30)",
            "Bedroom (SL_25_15_10)",
            "Master Bedroom (SL_25_15_30)",
            "Kids Bedroom (SL_25_15_10)",
            "Guest Bedroom (SL_25_15_10)",
            "Kitchen (SL_25_30_30)",
            "Kitchenette (SL_25_30_30)",
            "Bathroom (SL_25_20_10)",
            "Toilet / WC (SL_25_20_74)",
            "Powder Room (SL_25_20_74)",
            "Balcony (SL_25_60_10)",
            "Terrace (SL_25_60_47)",
            "Entry / Foyer (SL_25_35_47)",
            "Corridor (SL_25_35_30)",
            "Lobby (SL_25_35_47)",
            "Utility / Wash (SL_25_40_74)",
            "Store Room (SL_25_40_74)",
            "Study / Home Office (SL_25_10_74)",
            "Puja Room (SL_25_10_74)",
            "Parking / Garage (SL_25_50_47)",
            "Servant Room (SL_25_15_10)",
            "Gym (SL_25_10_30)",
        ],
        "psets": {
            "Pset_SpaceCommon": {
                "OccupancyType":  {"type": "select", "options": [
                    "LIVING", "DINING", "BEDROOM", "KITCHEN", "BATHROOM",
                    "TOILET", "BALCONY", "CORRIDOR", "LOBBY", "UTILITY",
                    "STORE", "STUDY", "PARKING", "PUJA", "GYM", "OTHER"
                ], "default": "LIVING"},
                "FloorFinish":    {"type": "select", "options": [
                    "Marble", "Vitrified Tiles", "Anti-skid Tiles",
                    "Wooden Flooring", "Granite", "Ceramic Tiles",
                    "Epoxy", "Carpet", "Kota Stone", "IPS"
                ], "default": "Vitrified Tiles"},
                "WallFinish":     {"type": "select", "options": [
                    "Plastic Emulsion", "Texture Paint", "Tiles",
                    "Wallpaper", "Exposed Brick", "Lime Plaster", "Distemper"
                ], "default": "Plastic Emulsion"},
                "CeilingFinish":  {"type": "select", "options": [
                    "POP", "Gypsum Board", "PVC Panel", "Wooden",
                    "Exposed Concrete", "False Ceiling"
                ], "default": "POP"},
                "IsExternal":     {"type": "bool",   "default": False},
                "GrossFloorArea": {"type": "number", "unit": "m2"},
                "NetFloorArea":   {"type": "number", "unit": "m2"},
                "Height":         {"type": "number", "unit": "m", "default": 2.7},
                "FireRating":     {"type": "select", "options": ["None", "30 min", "60 min", "120 min"], "default": "None"},
            },
            "Pset_SpaceThermal": {
                "VentilationType":    {"type": "select", "options": ["Natural", "Mechanical", "Mixed", "None"], "default": "Natural"},
                "AirChangesPerHour":  {"type": "number", "default": 6},
                "DesignTemperature":  {"type": "number", "unit": "C", "default": 22},
            },
            "Pset_SpaceLighting": {
                "LightingLevel":      {"type": "number", "unit": "lux", "default": 300},
                "ArtificialLighting": {"type": "bool", "default": True},
            },
            "Pset_SpaceAcoustic": {
                "AcousticRating":  {"type": "select", "options": ["Low", "Medium", "High"], "default": "Medium"},
                "SoundInsulation": {"type": "number", "unit": "dB", "default": 50},
            },
        }
    },
    "Door": {
        "ifc_class": "IfcDoor",
        "subtypes": ["Single Swing", "Double Swing", "Sliding", "Folding", "Revolving", "Flush", "Arched", "Pivot"],
        "psets": {
            "Pset_DoorCommon": {
                "OperationType":       {"type": "select", "options": ["SINGLE_SWING_LEFT", "SINGLE_SWING_RIGHT", "DOUBLE_SWING", "SLIDING", "FOLDING", "REVOLVING", "FIXED", "PIVOT"], "default": "SINGLE_SWING_RIGHT"},
                "OverallWidth":        {"type": "number", "unit": "m", "default": 0.9},
                "OverallHeight":       {"type": "number", "unit": "m", "default": 2.1},
                "Material":            {"type": "text",   "options": ["Teak Wood", "Flush Door", "UPVC", "Aluminium", "Glass", "Steel"], "default": "Teak Wood"},
                "Finish":              {"type": "text",   "options": ["Painted", "Polished", "Laminated", "Veneer", "Anodized"], "default": "Painted"},
                "FireRating":          {"type": "text",   "options": ["None", "30 min", "60 min", "90 min", "120 min"], "default": "None"},
                "IsExternal":          {"type": "bool",   "default": False},
                "SecurityRating":      {"type": "text",   "options": ["Low", "Medium", "High"], "default": "Medium"},
                "DoorLeafs":           {"type": "number", "default": 1},
                "ThresholdHeight":     {"type": "number", "unit": "m", "default": 0.05},
                "IsAccessible":        {"type": "bool",   "default": True},
            }
        }
    },
    "Window": {
        "ifc_class": "IfcWindow",
        "subtypes": ["Sliding", "Casement", "Awning", "Fixed", "Louvered", "Bay", "Skylight"],
        "psets": {
            "Pset_WindowCommon": {
                "OperationType":        {"type": "select", "options": ["SLIDING", "CASEMENT", "AWNING", "FIXED", "LOUVERED", "TILT_AND_TURN"], "default": "SLIDING"},
                "OverallWidth":         {"type": "number", "unit": "m", "default": 1.2},
                "OverallHeight":        {"type": "number", "unit": "m", "default": 1.2},
                "Material":             {"type": "text",   "options": ["Aluminium", "UPVC", "Wood", "Steel"], "default": "Aluminium"},
                "FrameMaterial":        {"type": "text",   "options": ["Aluminium", "Wood", "UPVC", "Steel"], "default": "Aluminium"},
                "GlazingType":          {"type": "text",   "options": ["Single", "Double", "Triple", "Tinted", "Frosted"], "default": "Double"},
                "ThermalTransmittance": {"type": "number", "unit": "W/m²K", "default": 3.0},
                "UValue":               {"type": "number", "unit": "W/m²K", "default": 2.5},
                "CillHeight":           {"type": "number", "unit": "m", "default": 0.9},
                "IsExternal":           {"type": "bool",   "default": True},
            }
        }
    },
    "Wall": {
        "ifc_class": "IfcWall",
        "subtypes": ["Exterior", "Interior", "Partition", "Retaining", "Curtain"],
        "psets": {
            "Pset_WallCommon": {
                "Material":       {"type": "text",   "options": ["Brick", "AAC Block", "RCC", "Drywall", "Glass"], "default": "Brick"},
                "Thickness":      {"type": "number", "unit": "mm", "default": 230},
                "Height":         {"type": "number", "unit": "m",  "default": 3.0},
                "OverallHeight":  {"type": "number", "unit": "m",  "default": 3.0},
                "Width":          {"type": "number", "unit": "m",  "default": 0.23},
                "OverallWidth":   {"type": "number", "unit": "m",  "default": 0.23},
                "FireRating":     {"type": "text",   "options": ["None", "30 min", "60 min", "120 min"], "default": "None"},
                "IsExternal":     {"type": "bool",   "default": False},
                "LoadBearing":    {"type": "bool",   "default": True},
                "Finish":         {"type": "text",   "options": ["Plaster", "Tiles", "Paint", "Exposed Brick"], "default": "Plaster"},
            }
        }
    },
    "Furniture": {
        "ifc_class": "IfcFurniture",
        "subtypes": ["Sofa", "Sofa Set", "L-Shaped Sofa", "Recliner", "Bed", "Wardrobe", "Dining Table",
                     "Dining Chair", "Chair", "Accent Chair", "TV Unit", "Study Table", "Bookshelf",
                     "Cabinet", "Coffee Table", "Centre Table", "Side Table", "Dressing Table",
                     "Bar Stool", "Bean Bag", "Shoe Rack", "Pooja Mandir"],
        "psets": {
            "Pset_FurnitureTypeCommon": {
                "FurnitureType":   {"type": "select", "options": ["CHAIR", "TABLE", "DESK", "BED", "FILECABINET", "SHELF", "SOFA", "USERDEFINED", "NOTDEFINED"], "default": "NOTDEFINED"},
                "Style":          {"type": "text",   "options": ["Modern", "Contemporary", "Classic", "Minimalist", "Industrial", "Bohemian", "Scandinavian"], "default": "Modern"},
                "Material":       {"type": "text",   "options": ["Teak Wood", "Sheesham Wood", "MDF", "Plywood", "Metal", "Rattan", "Acrylic", "Glass"], "default": "MDF"},
                "Finish":         {"type": "text",   "options": ["Laminate", "Veneer", "Paint", "Polish", "Fabric", "Leather", "Lacquer"], "default": "Laminate"},
                "Color":          {"type": "color",  "default": "#8B6914"},
                "OverallWidth":   {"type": "number", "unit": "m", "default": 0.8},
                "OverallDepth":   {"type": "number", "unit": "m", "default": 0.8},
                "OverallHeight":  {"type": "number", "unit": "m", "default": 0.8},
                "Manufacturer":   {"type": "text", "options": ["Urban Ladder", "Pepperfry", "IKEA", "Godrej Interio", "Durian", "Nilkamal", "HomeTown"], "default": "Urban Ladder"},
                "ModelNumber":    {"type": "text", "default": "Standard"},
                "Weight":         {"type": "number", "unit": "kg", "default": 50},
                "WarrantyYears":  {"type": "number", "default": 2},
                "AssemblyRequired": {"type": "bool", "default": False},
            },
            "Pset_SofaTypeCommon": {
                "SeatingCapacity":    {"type": "number", "default": 3},
                "SofaConfiguration":  {"type": "select", "options": ["2-Seater", "3-Seater", "L-Shaped", "U-Shaped", "Sectional", "Recliner", "Sofa Cum Bed"], "default": "3-Seater"},
                "UpholsteryMaterial": {"type": "text", "options": ["Leather", "Leatherette", "Fabric", "Velvet", "Microfiber", "Suede"], "default": "Fabric"},
                "UpholsteryColor":    {"type": "text", "options": ["Beige", "Grey", "Brown", "Navy Blue", "Dark Green", "Off White", "Mustard"], "default": "Grey"},
                "FrameMaterial":      {"type": "text", "options": ["Solid Wood", "Metal", "Plywood", "Hardwood"], "default": "Solid Wood"},
                "CushionFilling":     {"type": "text", "options": ["High Density Foam", "Memory Foam", "Feather", "Fibre"], "default": "High Density Foam"},
                "HasSleepFunction":   {"type": "bool", "default": False},
                "HasStorage":         {"type": "bool", "default": False},
                "LegMaterial":        {"type": "text", "options": ["Wood", "Stainless Steel", "Plastic"], "default": "Wood"},
            },
            "Pset_BedTypeCommon": {
                "BedSize":            {"type": "select", "options": ["Single (90x190)", "Double (120x190)", "Queen (150x190)", "King (180x200)", "Super King (200x200)"], "default": "Queen (150x190)"},
                "StorageType":        {"type": "select", "options": ["None", "Hydraulic Box", "Drawer Storage", "Box Storage"], "default": "Hydraulic Box"},
                "HasHeadboard":       {"type": "bool", "default": True},
                "HeadboardMaterial":  {"type": "text", "options": ["Teak Wood", "MDF", "Upholstered", "Metal"], "default": "Teak Wood"},
                "MattressIncluded":   {"type": "bool", "default": False},
                "MattressType":       {"type": "text", "options": ["Coir", "Foam", "Spring", "Orthopedic", "Memory Foam", "Latex"], "default": "Orthopedic"},
                "BedFrameMaterial":   {"type": "text", "options": ["Teak Wood", "Sheesham Wood", "MDF", "Metal", "Engineered Wood"], "default": "Teak Wood"},
                "IsFolding":          {"type": "bool", "default": False},
            },
            "Pset_ChairTypeCommon": {
                "ChairType":      {"type": "select", "options": ["Dining Chair", "Accent Chair", "Arm Chair", "Bar Stool", "Office Chair", "Lounge Chair", "Rocking Chair"], "default": "Dining Chair"},
                "IsErgonomic":    {"type": "bool", "default": False},
                "SeatingHeight":  {"type": "number", "unit": "m", "default": 0.45},
                "HasArmRest":     {"type": "bool", "default": False},
                "HasWheels":      {"type": "bool", "default": False},
                "SeatMaterial":   {"type": "text", "options": ["Fabric", "Leather", "Plastic", "Wood", "Mesh"], "default": "Fabric"},
                "MaxLoadCapacity": {"type": "number", "unit": "kg", "default": 120},
            },
            "Pset_TableTypeCommon": {
                "TableShape":     {"type": "select", "options": ["Rectangular", "Round", "Square", "Oval", "6-Seater", "4-Seater"], "default": "Rectangular"},
                "SeatingCapacity":{"type": "number", "default": 4},
                "TabletopMaterial":{"type": "text", "options": ["Teak Wood", "Glass", "Marble", "Granite", "MDF", "Metal"], "default": "Teak Wood"},
                "LegMaterial":    {"type": "text", "options": ["Wood", "Metal", "Glass", "Plastic"], "default": "Wood"},
                "IsExtendable":   {"type": "bool", "default": False},
            },
            "Pset_CabinetTypeCommon": {
                "NumberOfShelves": {"type": "number", "default": 3},
                "NumberOfDoors":   {"type": "number", "default": 2},
                "DoorType":        {"type": "select", "options": ["Sliding", "Hinged", "Open", "Folding", "Shutter"], "default": "Sliding"},
                "CableManagement": {"type": "bool", "default": False},
                "MountingType":    {"type": "select", "options": ["Floor-mounted", "Wall-mounted", "Built-in", "Modular"], "default": "Floor-mounted"},
                "HasMirror":       {"type": "bool", "default": False},
                "HasLock":         {"type": "bool", "default": False},
                "InteriorFinish":  {"type": "text", "options": ["Laminate", "Paint", "Fabric", "None"], "default": "Laminate"},
            },
            "Pset_TVUnitTypeCommon": {
                "TVSizeCompatible":  {"type": "text", "options": ["Up to 43 inch", "Up to 55 inch", "Up to 65 inch", "Up to 75 inch", "80+ inch"], "default": "Up to 55 inch"},
                "NumberOfShelves":   {"type": "number", "default": 2},
                "HasCableManagement":{"type": "bool", "default": True},
                "HasDrawers":        {"type": "bool", "default": True},
                "WallMounted":       {"type": "bool", "default": False},
                "FinishMaterial":    {"type": "text", "options": ["High Gloss White", "Walnut Veneer", "Wenge", "Oak", "Matte Grey"], "default": "High Gloss White"},
            },
            "Pset_WardrobeTypeCommon": {
                "NumberOfDoors":     {"type": "number", "default": 3},
                "DoorType":          {"type": "select", "options": ["Sliding", "Hinged", "Folding"], "default": "Sliding"},
                "HasMirror":         {"type": "bool", "default": True},
                "InternalLayout":    {"type": "text", "options": ["Standard", "With Drawers", "With Trouser Rack", "Full Shelves", "Custom"], "default": "With Drawers"},
                "NumberOfShelves":   {"type": "number", "default": 4},
                "NumberOfDrawers":   {"type": "number", "default": 2},
                "HasHangingRod":     {"type": "bool", "default": True},
                "LockType":          {"type": "text", "options": ["No Lock", "Key Lock", "Handle Lock"], "default": "Handle Lock"},
                "BodyMaterial":      {"type": "text", "options": ["MDF", "Plywood", "Particle Board", "Solid Wood"], "default": "MDF"},
            },
            "Pset_DiningSetTypeCommon": {
                "Configuration":     {"type": "select", "options": ["2-Seater", "4-Seater", "6-Seater", "8-Seater"], "default": "6-Seater"},
                "TableShape":        {"type": "select", "options": ["Rectangular", "Round", "Square", "Oval"], "default": "Rectangular"},
                "ChairMaterial":     {"type": "text", "options": ["Wood", "Metal", "Plastic", "Upholstered"], "default": "Wood"},
            },
        }
    },
    "FlowTerminal": {
        "ifc_class": "IfcSanitaryTerminal",
        "subtypes": ["WC / Toilet", "Wash Basin", "Kitchen Sink", "Shower", "Bathtub", "Urinal"],
        "psets": {
            "Pset_SanitaryTerminalTypeCommon": {
                "SanitaryTerminalType": {"type": "select", "options": ["BATH", "BIDET", "CISTERN", "SHOWER", "SINK", "SANITARYFOUNTAIN", "TOILETPAN", "URINAL", "WASHHANDBASIN", "WCSEAT", "USERDEFINED", "NOTDEFINED"], "default": "WASHHANDBASIN"},
                "Material":    {"type": "text",   "options": ["Ceramic", "Porcelain", "Acrylic", "Stainless Steel", "Cast Iron"], "default": "Ceramic"},
                "Color":       {"type": "color",  "default": "#FFFFFF"},
                "Mounting":    {"type": "select", "options": ["Wall-hung", "Floor-mounted", "Counter-top", "Under-mount"], "default": "Wall-hung"},
                "MountingType": {"type": "select", "options": ["Countertop", "Pedestal", "Wall-hung", "Floor-mounted", "Built-in"], "default": "Wall-hung"},
                "FlushType":   {"type": "text",   "options": ["Single Flush", "Dual Flush", "Sensor"], "default": "Dual Flush"},
                "SpigotPosition": {"type": "text", "options": ["Top", "Back", "Side", "Floor"], "default": "Back"},
                "BowlCount":    {"type": "number", "default": 1},
                "HasDrainer":   {"type": "bool", "default": False},
                "TrayMaterial": {"type": "text", "options": ["Acrylic", "Ceramic", "Stone Resin", "Steel"], "default": "Acrylic"},
                "DrainDiameter": {"type": "number", "unit": "m", "default": 0.05},
                "WaterCapacity": {"type": "number", "unit": "L", "default": 150},
                "Shape":        {"type": "text", "options": ["Freestanding", "Built-in", "Rectangular", "Oval", "Corner"], "default": "Built-in"},
                "WaterResistance": {"type": "text", "options": ["Low", "Medium", "High"], "default": "High"},
                "Manufacturer":{"type": "text",   "options": ["Kohler", "Jaquar", "Hindware", "Cera", "American Standard"], "default": "Jaquar"},
                "InstallationHeight": {"type": "number", "unit": "m", "default": 0.85},
                "OverallWidth":   {"type": "number", "unit": "m", "default": 0.6},
                "OverallDepth":   {"type": "number", "unit": "m", "default": 0.6},
                "OverallHeight":  {"type": "number", "unit": "m", "default": 0.8},
            }
        }
    },
    "ElectricAppliance": {
        "ifc_class": "IfcElectricAppliance",
        "subtypes": ["Refrigerator", "Single Door Fridge", "Double Door Fridge", "Side-by-Side Fridge",
                     "Washing Machine", "Front Load Washer", "Top Load Washer", "Dishwasher",
                     "Microwave", "OTG", "Convection Microwave",
                     "Gas Stove", "Induction Cooktop", "Chimney / Hood", "Cooking Range",
                     "Split AC", "Window AC", "Cassette AC", "Portable AC",
                     "Ceiling Fan", "Exhaust Fan", "Pedestal Fan",
                     "Water Heater / Geyser", "Water Purifier / RO",
                     "Television / TV", "Air Purifier", "Mixer Grinder"],
        "psets": {
            "Pset_ElectricApplianceTypeCommon": {
                "ApplianceType": {"type": "select", "options": ["DISHWASHER", "ELECTRICCOOKER", "FREEZER", "FRIDGE_FREEZER", "KITCHENMACHINE", "MICROWAVE", "REFRIGERATOR", "TUMBLEDRYER", "WASHINGMACHINE", "USERDEFINED", "NOTDEFINED"], "default": "REFRIGERATOR"},
                "PowerRating":   {"type": "number", "unit": "W", "default": 1000},
                "Voltage":       {"type": "number", "unit": "V", "default": 230},
                "Color":         {"type": "color",  "default": "#C0C0C0"},
                "Manufacturer":  {"type": "text",   "options": ["Samsung", "LG", "Whirlpool", "Bosch", "IFB", "Voltas", "Daikin", "Haier", "Godrej", "Bajaj"], "default": "LG"},
                "ModelNumber":   {"type": "text", "default": "Standard Model"},
                "EnergyRating":  {"type": "select", "options": ["1 Star", "2 Star", "3 Star", "4 Star", "5 Star"], "default": "3 Star"},
                "OverallWidth":  {"type": "number", "unit": "m", "default": 0.7},
                "OverallDepth":  {"type": "number", "unit": "m", "default": 0.7},
                "OverallHeight": {"type": "number", "unit": "m", "default": 1.5},
            },
            "Pset_RefrigeratorTypeCommon": {
                "RefrigeratorType":  {"type": "select", "options": ["Single Door", "Double Door", "Side-by-Side", "French Door", "Mini Fridge"], "default": "Double Door"},
                "TotalCapacity":     {"type": "number", "unit": "L", "default": 310},
                "FreezerCapacity":   {"type": "number", "unit": "L", "default": 80},
                "FreshFoodCapacity": {"type": "number", "unit": "L", "default": 230},
                "InverterCompressor":{"type": "bool", "default": True},
                "HasWaterDispenser": {"type": "bool", "default": False},
                "AnnualPowerConsumption": {"type": "number", "unit": "kWh", "default": 250},
            },
            "Pset_WashingMachineTypeCommon": {
                "WashingMachineType": {"type": "select", "options": ["Front Load", "Top Load", "Semi-Automatic"], "default": "Front Load"},
                "LoadCapacity":      {"type": "number", "unit": "kg", "default": 7},
                "SpinSpeed":         {"type": "number", "unit": "RPM", "default": 1200},
                "NumberOfPrograms":  {"type": "number", "default": 15},
                "HasDryer":          {"type": "bool", "default": False},
                "WaterConsumption":  {"type": "number", "unit": "L", "default": 50},
                "InverterMotor":     {"type": "bool", "default": True},
            },
            "Pset_GasStoveTypeCommon": {
                "BurnerCount":       {"type": "select", "options": ["2 Burner", "3 Burner", "4 Burner", "5 Burner"], "default": "3 Burner"},
                "FuelType":          {"type": "select", "options": ["LPG", "PNG", "Electric", "Induction"], "default": "LPG"},
                "StoveType":         {"type": "select", "options": ["Glass Top", "Stainless Steel", "Cast Iron", "Induction"], "default": "Glass Top"},
                "AutoIgnition":      {"type": "bool", "default": True},
                "HasGrids":          {"type": "bool", "default": True},
            },
            "Pset_AirConditionerTypeCommon": {
                "ACType":            {"type": "select", "options": ["Split AC", "Window AC", "Cassette AC", "Tower AC", "Portable AC"], "default": "Split AC"},
                "Tonnage":           {"type": "select", "options": ["0.75 Ton", "1 Ton", "1.5 Ton", "2 Ton", "2.5 Ton"], "default": "1.5 Ton"},
                "EnergyRating":      {"type": "select", "options": ["1 Star", "2 Star", "3 Star", "4 Star", "5 Star"], "default": "3 Star"},
                "HasInverter":       {"type": "bool", "default": True},
                "HasWifi":           {"type": "bool", "default": False},
                "CoolantType":       {"type": "text", "options": ["R-32", "R-410A", "R-22"], "default": "R-32"},
                "HasAutoClean":      {"type": "bool", "default": False},
                "PowerRating":       {"type": "number", "unit": "W", "default": 1500},
            },
            "Pset_TelevisionTypeCommon": {
                "ScreenSize":        {"type": "select", "options": ["32 inch", "40 inch", "43 inch", "50 inch", "55 inch", "65 inch", "75 inch"], "default": "55 inch"},
                "DisplayType":       {"type": "select", "options": ["LED", "OLED", "QLED", "4K UHD", "Full HD"], "default": "4K UHD"},
                "IsSmartTV":         {"type": "bool", "default": True},
                "HDMIPorts":         {"type": "number", "default": 3},
                "HasWifi":           {"type": "bool", "default": True},
                "HasBluetooth":      {"type": "bool", "default": True},
                "RefreshRate":       {"type": "number", "unit": "Hz", "default": 60},
                "PowerRating":       {"type": "number", "unit": "W", "default": 150},
            },
            "Pset_WaterHeaterTypeCommon": {
                "HeaterType":        {"type": "select", "options": ["Storage", "Instant", "Solar", "Heat Pump"], "default": "Storage"},
                "Capacity":          {"type": "number", "unit": "L", "default": 15},
                "PowerRating":       {"type": "number", "unit": "W", "default": 2000},
                "HasSafetyValve":    {"type": "bool", "default": True},
                "TankMaterial":      {"type": "text", "options": ["Stainless Steel", "Glass Lined", "Copper"], "default": "Glass Lined"},
                "MountingType":      {"type": "select", "options": ["Wall-mounted", "Vertical", "Horizontal"], "default": "Wall-mounted"},
            },
            "Pset_CeilingFanTypeCommon": {
                "BladeSpan":         {"type": "select", "options": ["900 mm", "1050 mm", "1200 mm", "1400 mm"], "default": "1200 mm"},
                "NumberOfBlades":    {"type": "number", "default": 3},
                "SpeedSettings":     {"type": "number", "default": 5},
                "PowerRating":       {"type": "number", "unit": "W", "default": 75},
                "HasRemote":         {"type": "bool", "default": False},
                "HasLED":            {"type": "bool", "default": False},
                "BladeMaterial":     {"type": "text", "options": ["Aluminium", "ABS Plastic", "Wood", "Steel"], "default": "ABS Plastic"},
            },
            "Pset_WaterPurifierTypeCommon": {
                "PurificationTechnology": {"type": "select", "options": ["RO", "UV", "UF", "RO+UV", "RO+UV+UF"], "default": "RO+UV"},
                "StorageCapacity":   {"type": "number", "unit": "L", "default": 8},
                "PurificationCapacity": {"type": "number", "unit": "L/hr", "default": 12},
                "MountingType":      {"type": "select", "options": ["Wall-mounted", "Counter-top", "Under-sink"], "default": "Wall-mounted"},
                "HasTDSController":  {"type": "bool", "default": True},
                "InputTDS":          {"type": "number", "unit": "ppm", "default": 2000},
            },
            "Pset_MicrowaveTypeCommon": {
                "MicrowaveType":     {"type": "select", "options": ["Solo", "Grill", "Convection", "OTG"], "default": "Convection"},
                "CavityVolume":      {"type": "number", "unit": "L", "default": 28},
                "MaxPowerOutput":    {"type": "number", "unit": "W", "default": 900},
                "HasAutoDefrost":    {"type": "bool", "default": True},
                "HasChildLock":      {"type": "bool", "default": True},
                "PlatterDiameter":   {"type": "number", "unit": "m", "default": 0.315},
            },
        }
    },
    "Stair": {
        "ifc_class": "IfcStair",
        "subtypes": ["Straight", "L-shaped", "U-shaped", "Spiral", "Winder"],
        "psets": {
            "Pset_StairCommon": {
                "NumberOfRiser":  {"type": "number", "default": 15},
                "NumberOfTreads": {"type": "number", "default": 14},
                "RiserHeight":    {"type": "number", "unit": "mm", "default": 175},
                "TreadLength":    {"type": "number", "unit": "mm", "default": 250},
                "Material":       {"type": "text",   "options": ["RCC", "Steel", "Wood", "Marble", "Granite"], "default": "RCC"},
                "FireRating":     {"type": "text",   "options": ["None", "30 min", "60 min", "120 min"], "default": "None"},
            }
        }
    },
    "Column": {
        "ifc_class": "IfcColumn",
        "subtypes": ["RCC", "Steel", "Timber", "Composite"],
        "psets": {
            "Pset_ColumnCommon": {
                "Material":   {"type": "text",   "options": ["RCC", "Steel", "Timber", "Composite"], "default": "RCC"},
                "Width":      {"type": "number", "unit": "mm", "default": 300},
                "Depth":      {"type": "number", "unit": "mm", "default": 300},
                "FireRating": {"type": "text",   "options": ["None", "30 min", "60 min", "120 min"], "default": "None"},
            }
        }
    },
    "Slab": {
        "ifc_class": "IfcSlab",
        "subtypes": ["Floor Slab", "Roof Slab", "Stair Landing", "Ramp"],
        "psets": {
            "Pset_SlabCommon": {
                "Material":   {"type": "text",   "options": ["RCC", "Precast", "Composite"], "default": "RCC"},
                "Thickness":  {"type": "number", "unit": "mm", "default": 150},
                "FireRating": {"type": "text",   "options": ["None", "30 min", "60 min", "120 min"], "default": "None"},
                "Finish":     {"type": "text",   "options": ["Smooth", "Rough", "Polished"], "default": "Smooth"},
            }
        }
    },
    "LightFixture": {
        "ifc_class": "IfcLightFixture",
        "subtypes": ["Ceiling Light", "Pendant", "Recessed", "Wall Sconce", "Floor Lamp", "Track Light"],
        "psets": {
            "Pset_LightFixtureTypeCommon": {
                "LightFixtureType": {"type": "select", "options": ["POINTSOURCE", "DIRECTIONSOURCE", "SECURITYLIGHTING", "EMERGENCYLIGHTING"], "default": "POINTSOURCE"},
                "Wattage":    {"type": "number", "unit": "W", "default": 60},
                "LampType":   {"type": "select", "options": ["LED", "CFL", "Halogen", "Fluorescent", "Incandescent"], "default": "LED"},
                "Color":      {"type": "color",  "default": "#FFFFE0"},
                "ColorTemp":  {"type": "select", "options": ["Warm White (2700K)", "Neutral White (4000K)", "Cool White (6500K)"], "default": "Warm White (2700K)"},
                "Lumens":     {"type": "number", "unit": "lm", "default": 800},
                "Manufacturer": {"type": "text", "default": "Generic"},
            }
        }
    },
}

# Generic category/type registry used by the BIM compiler. The keys on the
# left are AI/cache-friendly names; the values are valid IFC4 enum values for
# the installed schema.
ENTITY_SCHEMA_ALIASES = {
    "IfcFurniture": "Furniture",
    "IfcFurnishingElement": "Furniture",
    "IfcSanitaryTerminal": "FlowTerminal",
    "SanitaryTerminal": "FlowTerminal",
    "IfcElectricAppliance": "ElectricAppliance",
}

COMPONENT_TYPE_MAP = {
    "furnishing": {
        "schema_key": "Furniture",
        "ifc_class": "IfcFurniture",
        "pset": "Pset_FurnitureTypeCommon",
        "predefined_attr": "PredefinedType",
        "type_property": "FurnitureType",
        "default_type": "NOTDEFINED",
        "type_psets": {
            "SOFA": ["Pset_SofaTypeCommon"],
            "BED": ["Pset_BedTypeCommon"],
            "CHAIR": ["Pset_ChairTypeCommon"],
            "TABLE": ["Pset_TableTypeCommon"],
            "DESK": ["Pset_TableTypeCommon"],
            "SHELF": ["Pset_CabinetTypeCommon", "Pset_WardrobeTypeCommon"],
            "FILECABINET": ["Pset_CabinetTypeCommon"],
            "TV_UNIT": ["Pset_TVUnitTypeCommon"],
            "WARDROBE": ["Pset_WardrobeTypeCommon"],
        },
        "types": {
            # Sofa family
            "sofa": "SOFA",
            "couch": "SOFA",
            "l_shaped_sofa": "SOFA",
            "sectional_sofa": "SOFA",
            "recliner": "SOFA",
            "sofa_cum_bed": "SOFA",
            "bean_bag": "CHAIR",
            # Bed family
            "bed": "BED",
            "single_bed": "BED",
            "double_bed": "BED",
            "queen_bed": "BED",
            "king_bed": "BED",
            "bunk_bed": "BED",
            "day_bed": "BED",
            # Chair family
            "chair": "CHAIR",
            "armchair": "CHAIR",
            "dining_chair": "CHAIR",
            "accent_chair": "CHAIR",
            "bar_stool": "CHAIR",
            "barstool": "CHAIR",
            "office_chair": "CHAIR",
            "lounge_chair": "CHAIR",
            # Table family
            "dining_table": "TABLE",
            "work_table": "TABLE",
            "coffee_table": "TABLE",
            "centre_table": "TABLE",
            "center_table": "TABLE",
            "side_table": "TABLE",
            "end_table": "TABLE",
            "console_table": "TABLE",
            "table": "TABLE",
            # Desk family
            "study_table": "DESK",
            "desk": "DESK",
            "writing_desk": "DESK",
            "dressing_table": "DESK",
            "dresser": "DESK",
            # Wardrobe / storage
            "wardrobe": "SHELF",
            "closet": "SHELF",
            "almirah": "SHELF",
            "bookshelf": "SHELF",
            "bookcase": "SHELF",
            "shelf": "SHELF",
            "shoe_rack": "SHELF",
            "pooja_mandir": "SHELF",
            "puja_mandir": "SHELF",
            # TV Unit
            "tv_unit": "SHELF",
            "tvunit": "SHELF",
            "tv_cabinet": "SHELF",
            "media_unit": "SHELF",
            "entertainment_unit": "SHELF",
            # Cabinet / storage
            "cabinet": "FILECABINET",
            "file_cabinet": "FILECABINET",
            "kitchen_cabinet": "FILECABINET",
            "crockery_unit": "FILECABINET",
            "display_cabinet": "FILECABINET",
        },
    },
    "appliance": {
        "schema_key": "ElectricAppliance",
        "ifc_class": "IfcElectricAppliance",
        "pset": "Pset_ElectricApplianceTypeCommon",
        "predefined_attr": "PredefinedType",
        "type_property": "ApplianceType",
        "default_type": "NOTDEFINED",
        "type_psets": {
            "REFRIGERATOR": ["Pset_RefrigeratorTypeCommon"],
            "FRIDGE_FREEZER": ["Pset_RefrigeratorTypeCommon"],
            "WASHINGMACHINE": ["Pset_WashingMachineTypeCommon"],
            "TUMBLEDRYER": ["Pset_WashingMachineTypeCommon"],
            "ELECTRICCOOKER": ["Pset_GasStoveTypeCommon"],
            "MICROWAVE": ["Pset_MicrowaveTypeCommon"],
            "USERDEFINED": [],
        },
        "types": {
            # Fridge
            "refrigerator": "REFRIGERATOR",
            "fridge": "REFRIGERATOR",
            "single_door_fridge": "REFRIGERATOR",
            "double_door_fridge": "FRIDGE_FREEZER",
            "side_by_side_fridge": "FRIDGE_FREEZER",
            "french_door_fridge": "FRIDGE_FREEZER",
            "freezer": "FREEZER",
            "fridge_freezer": "FRIDGE_FREEZER",
            # Washing
            "washing_machine": "WASHINGMACHINE",
            "washer": "WASHINGMACHINE",
            "front_load_washer": "WASHINGMACHINE",
            "top_load_washer": "WASHINGMACHINE",
            "semi_automatic": "WASHINGMACHINE",
            "dishwasher": "DISHWASHER",
            "dryer": "TUMBLEDRYER",
            # Cooking
            "microwave": "MICROWAVE",
            "otg": "MICROWAVE",
            "convection_microwave": "MICROWAVE",
            "oven": "ELECTRICCOOKER",
            "stove": "ELECTRICCOOKER",
            "gas_stove": "ELECTRICCOOKER",
            "hob": "ELECTRICCOOKER",
            "induction": "ELECTRICCOOKER",
            "induction_cooktop": "ELECTRICCOOKER",
            "cooking_range": "ELECTRICCOOKER",
            "cookingrange": "ELECTRICCOOKER",
            "cooktop": "ELECTRICCOOKER",
            "chimney": "USERDEFINED",
            "kitchen_chimney": "USERDEFINED",
            "chimney_hood": "USERDEFINED",
            # AC / fans
            "ac": "USERDEFINED",
            "split_ac": "USERDEFINED",
            "window_ac": "USERDEFINED",
            "air_conditioner": "USERDEFINED",
            "ceiling_fan": "USERDEFINED",
            "fan": "USERDEFINED",
            "exhaust_fan": "USERDEFINED",
            "pedestal_fan": "USERDEFINED",
            # Water
            "water_heater": "USERDEFINED",
            "geyser": "USERDEFINED",
            "water_purifier": "USERDEFINED",
            "ro": "USERDEFINED",
            "ro_purifier": "USERDEFINED",
            # Entertainment
            "television": "USERDEFINED",
            "tv": "USERDEFINED",
            "smart_tv": "USERDEFINED",
            "air_purifier": "USERDEFINED",
            # Small appliances
            "kitchen_machine": "KITCHENMACHINE",
            "mixer": "KITCHENMACHINE",
            "mixer_grinder": "KITCHENMACHINE",
            "grinder": "KITCHENMACHINE",
            "blender": "KITCHENMACHINE",
            "food_processor": "KITCHENMACHINE",
        },
    },
    "sanitary": {
        "schema_key": "FlowTerminal",
        "ifc_class": "IfcSanitaryTerminal",
        "pset": "Pset_SanitaryTerminalTypeCommon",
        "predefined_attr": "PredefinedType",
        "type_property": "SanitaryTerminalType",
        "default_type": "NOTDEFINED",
        "types": {
            "toilet": "TOILETPAN",
            "wc": "TOILETPAN",
            "commode": "TOILETPAN",
            "toilet_seat": "WCSEAT",
            "wc_seat": "WCSEAT",
            "wash_basin": "WASHHANDBASIN",
            "washbasin": "WASHHANDBASIN",
            "vanity_sink": "WASHHANDBASIN",
            "basin": "WASHHANDBASIN",
            "kitchen_sink": "SINK",
            "sink": "SINK",
            "shower": "SHOWER",
            "shower_tray": "SHOWER",
            "shower_cubicle": "SHOWER",
            "bathtub": "BATH",
            "bath": "BATH",
            "urinal": "URINAL",
            "bidet": "BIDET",
            "cistern": "CISTERN",
        },
    },
}

OPENING_TYPE_MAP = {
    "door": {
        "ifc_class": "IfcDoor",
        "schema_key": "Door",
        "pset": "Pset_DoorCommon",
        "predefined_attr": "PredefinedType",
        "predefined_type": "DOOR",
        "operation_attr": "OperationType",
        "operation_property": "OperationType",
        "default_operation": "SINGLE_SWING_RIGHT",
        "operations": {
            "single_swing_left": "SINGLE_SWING_LEFT",
            "left_swing": "SINGLE_SWING_LEFT",
            "single_swing_right": "SINGLE_SWING_RIGHT",
            "right_swing": "SINGLE_SWING_RIGHT",
            "double_swing_left": "DOUBLE_SWING_LEFT",
            "double_swing_right": "DOUBLE_SWING_RIGHT",
            "double_swing": "DOUBLE_DOOR_DOUBLE_SWING",
            "double_door": "DOUBLE_DOOR_SINGLE_SWING",
            "sliding": "SLIDING_TO_RIGHT",
            "sliding_left": "SLIDING_TO_LEFT",
            "sliding_right": "SLIDING_TO_RIGHT",
            "folding": "FOLDING_TO_RIGHT",
            "folding_left": "FOLDING_TO_LEFT",
            "folding_right": "FOLDING_TO_RIGHT",
            "revolving": "REVOLVING",
        },
    },
    "window": {
        "ifc_class": "IfcWindow",
        "schema_key": "Window",
        "pset": "Pset_WindowCommon",
        "predefined_attr": "PredefinedType",
        "predefined_type": "WINDOW",
        "operation_attr": "PartitioningType",
        "operation_property": "OperationType",
        "default_operation": "SINGLE_PANEL",
        "operations": {
            "sliding": "DOUBLE_PANEL_HORIZONTAL",
            "casement": "SINGLE_PANEL",
            "fixed": "SINGLE_PANEL",
            "fixedlight": "SINGLE_PANEL",
            "fixed_light": "SINGLE_PANEL",
            "double_panel": "DOUBLE_PANEL_VERTICAL",
            "triple_panel": "TRIPLE_PANEL_VERTICAL",
        },
    },
}

# Global property sets applied to all entities
GLOBAL_PSETS = {
    "Pset_Common": {
        "CreationDate": {"type": "text", "default": "2024-05-30"},
        "LastModifiedDate": {"type": "text", "default": "2024-05-30"},
    }
}

# Material library for IfcMaterial
MATERIALS = {
    "Concrete":        {"color": [0.7, 0.7, 0.7], "category": "Structure"},
    "Brick":           {"color": [0.8, 0.4, 0.2], "category": "Masonry"},
    "Marble":          {"color": [0.95, 0.95, 0.95], "category": "Finish"},
    "Teak Wood":       {"color": [0.55, 0.27, 0.07], "category": "Wood"},
    "Sheesham Wood":   {"color": [0.45, 0.22, 0.08], "category": "Wood"},
    "Ceramic":         {"color": [0.9, 0.9, 0.9], "category": "Finish"},
    "Glass":           {"color": [0.7, 0.9, 1.0], "category": "Transparent"},
    "Steel":           {"color": [0.75, 0.75, 0.8], "category": "Metal"},
    "Aluminium":       {"color": [0.85, 0.85, 0.85], "category": "Metal"},
    "Granite":         {"color": [0.4, 0.4, 0.4], "category": "Finish"},
    "Plywood":         {"color": [0.82, 0.71, 0.55], "category": "Wood"},
    "Stainless Steel": {"color": [0.8, 0.8, 0.82], "category": "Metal"},
    "Porcelain":       {"color": [0.95, 0.95, 0.95], "category": "Finish"},
    "Acrylic":         {"color": [0.9, 0.95, 1.0], "category": "Plastic"},
    "Leather":         {"color": [0.4, 0.2, 0.1], "category": "Fabric"},
    "Leatherette":     {"color": [0.35, 0.18, 0.08], "category": "Fabric"},
    "Fabric":          {"color": [0.6, 0.6, 0.8], "category": "Fabric"},
    "Velvet":          {"color": [0.25, 0.18, 0.45], "category": "Fabric"},
    "MDF":             {"color": [0.78, 0.68, 0.52], "category": "Wood"},
    "High Gloss White":{"color": [0.95, 0.95, 0.97], "category": "Finish"},
    "Wenge":           {"color": [0.22, 0.16, 0.1],  "category": "Wood"},
    "Walnut":          {"color": [0.39, 0.25, 0.12], "category": "Wood"},
    "ABS Plastic":     {"color": [0.88, 0.88, 0.88], "category": "Plastic"},
    "Painted White":   {"color": [0.97, 0.97, 0.97], "category": "Finish"},
}


def get_schema(cls_name: str) -> dict:
    """Get schema for a given class name."""
    cls_name = ENTITY_SCHEMA_ALIASES.get(cls_name, cls_name)
    return IFC_SCHEMA.get(cls_name, {})


def get_default_pset(cls_name: str) -> dict:
    """Return default property values for a class, including global standard sets."""
    schema = get_schema(cls_name)
    result = {}
    for pset_name, props in schema.get("psets", {}).items():
        result[pset_name] = {}
        for prop, meta in props.items():
            if "default" in meta:
                result[pset_name][prop] = meta["default"]

    for pset_name, props in GLOBAL_PSETS.items():
        result.setdefault(pset_name, {})
        for prop, meta in props.items():
            if "default" in meta:
                result[pset_name].setdefault(prop, meta["default"])
    return result


def get_standard_property_names(cls_name: str, flatten: bool = False):
    """Return standard property names for an IFC class.

    If flatten is False, returns a dict mapping PSet names to property name lists.
    If flatten is True, returns a sorted flat list of unique property names.
    """
    schema = get_schema(cls_name)
    result = {}

    for pset_name, props in schema.get("psets", {}).items():
        result[pset_name] = list(props.keys())

    for pset_name, props in GLOBAL_PSETS.items():
        result.setdefault(pset_name, [])
        result[pset_name].extend(props.keys())

    if flatten:
        flat = []
        for pset_props in result.values():
            for prop in pset_props:
                if prop not in flat:
                    flat.append(prop)
        return flat

    return result


def validate_pset(cls_name: str, pset_data: dict) -> dict:
    """Validate and clean pset data against schema."""
    schema = get_schema(cls_name)
    cleaned = {}
    for pset_name, props in pset_data.items():
        if pset_name not in schema.get("psets", {}):
            continue
        cleaned[pset_name] = {}
        for prop, value in props.items():
            if prop in schema["psets"][pset_name]:
                cleaned[pset_name][prop] = value
    return cleaned


# --- IFC schema introspection helpers --------------------------------------

def _get_ifc_schema_definition():
    try:
        return ifcopenshell.schema_by_name("IFC4")
    except Exception:
        return None


def _parse_enumeration_options(type_decl):
    text = str(type_decl)
    match = re.search(r"\(([^)]+)\)", text)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def _get_ifc_attribute_meta(type_decl):
    type_name = None
    if hasattr(type_decl, "name"):
        try:
            type_name = type_decl.name()
        except Exception:
            type_name = getattr(type_decl, "name", None)
    if not type_name:
        type_name = str(type_decl)
    if isinstance(type_name, str):
        type_name = type_name.lower()
    else:
        type_name = str(type_name).lower()

    if "boolean" in type_name:
        return {"type": "bool"}
    if "lengthmeasure" in type_name or ("ifcpositive" in type_name and "length" in type_name):
        return {"type": "number", "unit": "m"}
    if "areameasure" in type_name:
        return {"type": "number", "unit": "m2"}
    if "volumemeasure" in type_name:
        return {"type": "number", "unit": "m3"}
    if "label" in type_name or "text" in type_name or "identifier" in type_name:
        return {"type": "text"}
    if "enumeration" in str(type_decl).lower():
        options = _parse_enumeration_options(type_decl)
        return {"type": "select", "options": options}
    return {"type": "text"}


def get_entity_attributes(entity_name: str) -> list[dict]:
    """Return IFC4 direct entity attributes for an IFC entity type."""
    schema = _get_ifc_schema_definition()
    if schema is None:
        return []

    try:
        decl = schema.declaration_by_name(entity_name)
    except Exception:
        return []
    if decl is None:
        return []

    attrs = []
    for attr in decl.attributes():
        type_decl = attr.type_of_attribute().declared_type()
        meta = _get_ifc_attribute_meta(type_decl)
        declared_type_name = None
        if hasattr(type_decl, "name"):
            try:
                declared_type_name = type_decl.name()
            except Exception:
                declared_type_name = getattr(type_decl, "name", None)
        if not declared_type_name:
            declared_type_name = str(type_decl)
        attrs.append({
            "name": attr.name(),
            "optional": attr.optional(),
            "declared_type": declared_type_name,
            "type": meta["type"],
            "unit": meta.get("unit"),
            "options": meta.get("options", []),
        })
    return attrs


def generate_default_property_mapping(entity_name: str) -> dict:
    """Generate a fallback property set mapping for an IFC entity based on direct IFC attributes."""
    attrs = get_entity_attributes(entity_name)
    if not attrs:
        return {}

    pset_name = f"Pset_{entity_name[3:] if entity_name.startswith('Ifc') else entity_name}Common"
    mapping = {pset_name: {}}
    for attr in attrs:
        prop_meta = {
            "type": attr["type"],
        }
        if attr.get("unit"):
            prop_meta["unit"] = attr["unit"]
        if attr["type"] == "select" and attr["options"]:
            prop_meta["options"] = attr["options"]
            prop_meta["default"] = attr["options"][0]
        mapping[pset_name][attr["name"]] = prop_meta
    return mapping


def compare_entity_with_custom(entity_name: str) -> dict:
    """Compare direct IFC entity attributes with custom property schema definitions."""
    entity_attrs = {attr["name"] for attr in get_entity_attributes(entity_name)}
    custom_props = set(get_standard_property_names(entity_name, flatten=True))
    return {
        "entity_attributes": sorted(entity_attrs),
        "custom_property_names": sorted(custom_props),
        "missing_from_custom": sorted(entity_attrs - custom_props),
        "custom_extra": sorted(custom_props - entity_attrs),
    }
