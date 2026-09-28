# Domain Vision Statement — tiferet-plot

**Status:** Draft · **Domain:** `plot` · **Code:** `tiferet_plot/` (intended; not seeded) · **Branch:** `main`

## The bet: declare the plot, don't bury it in the drawing call

Most plots are made by writing a script that draws them. The script chooses a library, passes numbers into it, and saves a picture. From then on the picture is the only thing a reader can see, and the script is the only record of why the picture looks the way it does. Change the claim, the data, or the library, and someone has to re-read the script to find out what the figure was supposed to be.

tiferet-plot takes the opposite position. **The plot is a declared record, and the picture is a rendering of that record.** Declaring a plot means stating what it shows, which data it uses, and how that data should be marked. Drawing it is a later step, done by a tool that can be named and replaced. Matplotlib is the first such tool. It is not the definition of the plot.

## What this domain makes real

tiferet-plot is the home of a plot as data: a named figure, the data it depends on, and the marks that express that data. That record can be saved, retrieved, and rendered again. The picture a reader sees is produced from the record. It is not a substitute for it.

The same record is what a publication can carry and what a database can hold. This round keeps it in a file a paper or a report can sit beside. A database is the same kind of keeping, done later. Neither store is the plot. The plot is what they keep.

## What we get for it

### A figure you can ask about

A saved picture answers "what did this look like?" It does not answer "what was it supposed to show, from which data, and why these marks?" Those answers live in the record. A reader, or a later tool, can ask them without reconstructing a notebook.

### One claim, kept for a paper or a database

The costly object in a publication is not the pixels. It is the claim the figure makes, tied to the data behind it. When that claim is a record, a paper and a database can hold the same thing. Updating the claim updates what both of them are pointing at. Saving only the picture splits them.

### Drawing that can change without rewriting the plot

Matplotlib is how the first pictures are made. It is not how the plot is defined. A later drawing tool is another way to render the same record, not a reason to restate the figure. The plot does not take its meaning from the library that happens to draw it.

### Creating and showing, without copying either into every chart

Making a plot and looking at it belong to the tool a person is using, not to each kind of chart. A new kind does not have to re-teach that tool how to save, or how to display.

### Change that stays on the record

Renaming a series, pointing at different data, or changing the claim are edits to the record. The picture is rendered again from that edit. The cost does not grow with the number of scripts that used to draw the old version.

## The core of the work

Everything this domain does follows one path:

> **Declare** what the figure shows → **keep** that declaration as the record → **render** it to a picture → **show** the picture from the record.

Three things vary. The kind of chart. The tool that draws it. The place the record is kept. Declaring and keeping the plot is the same job in every combination of those.

The design commitment is: **the stored plot is the fixed point; the drawing tool and the store are the variable ends.** Line, scatter, and bar are the first kinds, enough to prove that a kind is part of the record and not a separate tool. Matplotlib is the first drawing tool. A file a publication can carry is the first store. More kinds, more drawing tools, and a database store are further ends on the same fixed point.

The kind and the drawing tool have to be supplied. A table of numbers does not say whether it is a line or a bar, and a saved plot does not say which library must draw it. Those inputs answer the question a picture cannot: what was this figure declared to be?

## What it deliberately does not do

It does not analyze data, fit a model, or decide which chart a claim deserves. The person declaring the plot brings that judgment. It does not replace Matplotlib, and it does not ship a second drawing library in this round. It does not run general applications or wire their parts together. That is the Tiferet framework. It does not publish the paper and it does not own a database. It produces the record those can hold, and the picture rendered from that record.

A database store, further chart kinds, and a command-line tool are later work, named so they are not quietly assumed here.

---

*Companion document:* `docs/core-domain-distillation.md` — the detailed walkthrough of the domain's vocabulary, behaviors, and the relationships between its parts.
