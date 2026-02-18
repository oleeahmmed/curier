## **Detailed Userflow (Step-by-step)**

I’ll describe this like a swimlane, but in text. Each step shows: **Actor → Action → System Behavior → Status**.

### **Stage 1: Booking & AWB Generation**

**3.1.1 Customer initiates shipment**

* **Actor:** Customer  
* **Action:**  
  * Visit your website or contact branch (phone / walk-in).  
  * Selects **“Send Parcel to Hong Kong”**.  
  * Fills form:  
    * Sender details (name, phone, address in Dhaka)  
    * Recipient details (name, phone, address in HK)  
    * Parcel details (contents, declared value, weight estimate, dimensions)  
    * Service type (Express)  
  * Chooses **Pickup from Address** or **Drop-off at Warehouse**.  
* **System:**  
  * Validates fields.  
  * Checks if route (Dhaka ➜ Hong Kong) and service type are available.  
  * Estimates cost (optional).  
* **Status (internal):** `DRAFT_SHIPMENT`

**3.1.2 Confirm booking & generate AWB**

* **Actor:** Customer or Dhaka Staff (if walk-in / phone booking)  
* **Action:**  
  * Confirms details and agrees to terms.  
  * Confirms payment method: Prepaid / Cash at warehouse / Credit account.  
* **System:**  
  * Creates Shipment record.  
  * Generates **unique AWB / Tracking Number**.  
  * Generates shipment QR/barcode.  
* **Status:** `BOOKED`

---

### **Stage 2: Parcel Arrival at Dhaka Warehouse**

This covers **both drop-off by customer** and **pickup by your driver**.

**3.2.1 Parcel physically arrives at warehouse**

* **Actor:** Dhaka Operations Staff  
* **Action:**  
  * Scans AWB barcode (from label or printed confirmation).  
  * Compares system data (weight, pieces, contents) with actual.  
  * Weighs and measures the parcel.  
* **System:**  
  * Pulls up Shipment record by AWB.  
  * Allows staff to adjust weight/dimensions (with audit log).  
  * If discrepancies, system flags **“Weight/Dimension Mismatch”** for review.  
* **Status:** `RECEIVED_AT_DHAKA_WAREHOUSE`

**3.2.2 Labeling & verification**

* **Actor:** Dhaka Staff  
* **Action:**  
  * Confirms packaging is acceptable.  
  * Prints and attaches:  
    * Shipping label with AWB barcode  
    * Any special handling labels (Fragile, Liquid, etc.)  
* **System:**  
  * Logs “Label printed” event with timestamp and user ID.  
* **Status:** `READY_FOR_SORTING`

**3.2.3 Sorting & bagging**

* **Actor:** Dhaka Staff  
* **Action:**  
  * Sorts parcels by destination (Hong Kong).  
  * Places parcels into **bags/containers** (e.g., HDK-BAG-001).  
  * Scans each parcel when putting into bag.  
* **System:**  
  * Links each AWB to a bag/container ID.  
  * Ensures no parcel is linked to two bags.  
* **Status:** `BAGGED_FOR_EXPORT`

---

### **Stage 3: Pre-flight Processing & Manifest Generation**

**3.3.1 Manifest creation**

* **Actor:** Dhaka Staff / Ops Manager  
* **Action:**  
  * Opens **“Create Manifest”** screen.  
  * Selects:  
    * Flight number (e.g., BG–XXX / CX–XXX via partner)  
    * Departure date & time  
    * Bag/container IDs to include.  
  * System lists all parcels in selected bags.  
* **System:**  
  * Validates:  
    * Parcel status is correct (no pending issues).  
    * Route \= Dhaka ➜ Hong Kong.  
  * Generates **Export Manifest**:  
    * Manifest ID  
    * Flight info  
    * List of AWBs (with weight, pieces, bag ID)  
* **Status (for parcels):** `IN_EXPORT_MANIFEST`

**3.3.2 Manifest finalization & print**

* **Actor:** Dhaka Ops Manager  
* **Action:**  
  * Reviews manifest totals.  
  * Confirms and locks the manifest.  
  * Prints manifest documents for airline/cargo handling.  
* **System:**  
  * Locks manifest from further edits.  
  * Stamps date/time \+ user.  
  * Optional: sends digital copy to HK office automatically.  
* **Status (for parcels):** `READY_FOR_AIRPORT_HANDOVER`

---

### **Stage 4: Handover to Airline / Departure from Dhaka**

**3.4.1 Handover to airport**

* **Actor:** Dhaka Staff (Airport / Line haul)  
* **Action:**  
  * Transports bags/containers to airport.  
  * At handover point, scans:  
    * Bag IDs  
    * Or each parcel (depending on process).  
* **System:**  
  * Logs **“Handed over to airline”** event.  
  * Captures airline/agent reference number.  
* **Status:** `HANDED_OVER_TO_AIRLINE`

**3.4.2 Flight departure**

* **Actor:** System / Dhaka Staff  
* **Action:**  
  * Staff updates the manifest as **“Departed”** after flight takeoff.  
  * OR system updates automatically via airline integration (if available).  
* **System:**  
  * Updates manifest status: `DEPARTED_FROM_DHAKA`.  
  * For all linked parcels, logs a tracking event:  
    * “Departed from Dhaka, en route to Hong Kong”.  
* **Status (for parcels):** `IN_TRANSIT_TO_HONGKONG`

---

