# Immune Cell Population Investigation
Author: Nathaniel Schoppa
Date: July 02 2026
---

## Introduction

Hello there Bob! As requested, I've delivered a tool for investigating immune cell populations.

To get things started, run the makefile and open a browser to http://localhost:8050/

The application creates a SQLite database called **teiko.db**. You can access it for future uses, but the application handles all the SQL calls. This should satisfy your requirement *part 1: data management*. The databased is structured according to the ERD below. Green are reference entities, blue are strong entities, and orange are weak entities.

![alt text](ERD.png)

From here, I'll cover the sectionds and where to find information.

---

## Section 1 - Data Overview: Cell Counts

This section contains a live, filterable datatable of per sample cell type proportions. Use the **Sort by Column**  dropdown (left) to sort the dataset, **Filter by Sample** and **Filter by Cell Type** dropdowns (middle and right) to select specific samples or cell types, and the orange **Download** button to download the current dataset snapshot as a CSV.

It should contain the information necessary to answer *part 2: initial analysis*, the frequency of each cell type in each sample. The dataset is formatted according to your specifications.

---

## Section 2 - Data Overview: Cell Counts

This sections contains a live boxplot of cell type proportions with selectable level and filters. If there is enough levels to by, then the section will additionally complete a multiple t-test and report adjusted p-values. Use the **Choose Factor-By Column** dropdown (left) to select comparison level and **Narrow Down Conditions** dropdown (right) to filter the data. Note that some filter combinations won't select any data; this is expected.

I've pre-loaded the filter and level to meet your request for **part 3: statistical analysis**: comparing PBMC samples of melanoma patients receiveing miraclib over response (yes or no). Excitingly, *cd4_t_cell* frequencies appear to differ between patients that respond to miracleb. Hopefully these tests should be of use to Yah D’yada.

---

## Section 3 - Cell Count Data

This section contains a live, filterable datatable of sample cell counts and metadata. The top row is a average sumamry for each cell type. Use the **Select Factors** dropdown (left) to choose which metadata columns to aggregate or compare over. By default, all columns are depicted. Note that if sample ids are shown, then the table depicts sample cell counts. If sample id is removed, then the table will depict averaged cell counts. Use the **Narrow Down Conditions** dropdown to filter the dataset. Note that, like in Section 2, some combinations will return no data. Use the **Toggle Proportions** button to swap the dataset between cell counts and cell type frequencies. Finally, like in Section 1, press the orange **Download** button to download the current dataset snapshot as a CSV.

Below the data table, there are two preset buttons to reset columns and filters. The top (1) will set filters to the default while the second removed the PBMC requirement but filters for male subjects. These two filters will aid completing **part 4: data subset analysis** of your request. Finally, below, there are bars depicting the unique metadata values present in the current selection. Use that to find the unique counts for each column and total number of subjects or samples, if appropriate.

Use the first filter (or default state) to find all melanoma PBMC samples at baseline from patients who have been treated with miraclib. From there, you can find how many samples from each project, how many subjects were responders/non-responders, and how many subjects were males/females. 

To determine the average number of B cells for melanoma male responders at baseline (not PBMC), use the second filter and look at the top summary row.

---

It has been a pleasure developing this for you, Bob. 

Please let me know if you encounter any issues with the application, or have a use case not covered.
