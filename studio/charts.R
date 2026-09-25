# Animated chart / infographic renderer for GeoExplainer.
# Rscript charts.R spec.json out_dir      -> out_dir/f000.png ... (transparent PNG frames, 30 fps)
# Each chart type has its own build-up animation; the last frame is the finished chart.
suppressPackageStartupMessages({
  library(jsonlite); library(ggplot2); library(ragg); library(systemfonts); library(scales)
})
args <- commandArgs(trailingOnly = TRUE)
sp <- fromJSON(args[1], simplifyVector = TRUE)
outdir <- args[2]
dir.create(outdir, showWarnings = FALSE, recursive = TRUE)
`%||%` <- function(a, b) if (is.null(a) || length(a) == 0 || identical(a, "")) b else a

fam <- "vidfont"
reg <- sp$font_regular %||% "C:/Windows/Fonts/Nirmala.ttc"
bold <- sp$font_bold %||% reg
try(register_font(fam, plain = reg, bold = bold), silent = TRUE)

bn <- identical(sp$lang %||% "bn", "bn")
unit <- sp$unit %||% ""
d2b <- function(x) if (bn) chartr("0123456789", "\u09e6\u09e7\u09e8\u09e9\u09ea\u09eb\u09ec\u09ed\u09ee\u09ef", x) else x
dec <- max(0, min(2, max(nchar(sub("^[^.]*\\.?", "", format(sp$data$value, scientific = FALSE, trim = TRUE))))))
num <- function(v, digits = dec) {
  s <- ifelse(abs(v) >= 1000, format(round(v), big.mark = ",", scientific = FALSE, trim = TRUE),
              formatC(v, format = "f", digits = digits))
  d2b(s)
}
fmt <- function(v) paste0(num(v), unit)
fmt_axis <- function(v) paste0(num(v, 0), unit)

look <- sp$look %||% "classic"
TH <- switch(look,
  hud = list(txt = "#f2f2f0", sub = "#8d9199", grid = "#ffffff1c", acc = "#e0283c",
             pal = c("#e0283c", "#f2f2f0", "#8d9199", "#ff7a7a", "#4a4f57", "#c9ccd1", "#a3121f")),
  light = list(txt = "#121212", sub = "#5c5c5c", grid = "#0000001a", acc = "#d6203a",
               pal = c("#d6203a", "#121212", "#7a7a7a", "#e98b8b", "#b0b0b0", "#3b3b3b", "#8c0f22")),
  list(txt = "#ffffff", sub = "#a9c1d6", grid = "#ffffff1f", acc = "#ffd166",
       pal = c("#ffd166", "#4895ef", "#e63946", "#2a9d8f", "#9d4edd", "#f4a261", "#52b788", "#ef476f")))

df <- as.data.frame(sp$data, stringsAsFactors = FALSE)
df$label <- d2b(as.character(df$label))
df$value <- as.numeric(df$value)
df <- df[!is.na(df$value), , drop = FALSE]
if (is.null(df$group)) df$group <- "a"
df$group <- as.character(df$group)
df$label <- factor(df$label, levels = unique(df$label))
multi <- length(unique(df$group)) > 1
n <- nrow(df)

W <- sp$w %||% 1600; H <- sp$h %||% 820
base <- max(18, round(W / 44))
tsize <- base / .pt * 1.05
NF <- sp$frames %||% 66          # frames of build-up (2.2 s)

ease <- function(x) { x <- pmin(1, pmax(0, x)); ifelse(x < 0.5, 4 * x^3, 1 - (-2 * x + 2)^3 / 2) }
# progress of element i of k when the whole build is at t (0..1), with a stagger
stag <- function(t, i, k, spread = 0.55) {
  if (k <= 1) return(ease(t))
  st <- (i - 1) / (k - 1) * spread
  ease((t - st) / (1 - spread))
}

theme_vid <- theme_minimal(base_family = fam, base_size = base) +
  theme(plot.background = element_rect(fill = "transparent", colour = NA),
        panel.background = element_rect(fill = "transparent", colour = NA),
        text = element_text(colour = TH$txt), axis.text = element_text(colour = TH$sub),
        axis.title = element_blank(), panel.grid.minor = element_blank(),
        panel.grid.major.x = element_blank(), panel.grid.major.y = element_line(colour = TH$grid, linewidth = 0.6),
        legend.position = "top", legend.title = element_blank(),
        legend.text = element_text(colour = TH$txt, size = base * 0.9),
        plot.margin = margin(10, 20, 10, 10))
fillv <- scale_fill_manual(values = rep(TH$pal, 5))
colv <- scale_colour_manual(values = rep(TH$pal, 5))
kind <- sp$kind %||% "bar"
vmax <- max(df$value, 0); vmin <- min(df$value, 0)
frame_plot <- function(t) {
  if (kind %in% c("hbar", "lollipop")) {
    d <- df[order(df$value), ]; d$label <- factor(d$label, levels = d$label)
    k <- nrow(d)
    # biggest first: ranking reveals from the top
    d$p <- sapply(seq_len(k), function(i) stag(t, k - i + 1, k))
    d$v <- d$value * d$p
    d$lab <- ifelse(d$p > 0.03, fmt(d$v), "")
    g <- ggplot(d, aes(label, v))
    g <- if (kind == "hbar") g + geom_col(fill = TH$acc, width = 0.62, alpha = pmin(1, d$p * 3)) else
      g + geom_segment(aes(xend = label, y = 0, yend = v), colour = TH$sub, linewidth = 1.4) +
          geom_point(colour = TH$acc, size = base / 2.2 * pmin(1, d$p * 2))
    return(g + geom_text(aes(label = lab), hjust = -0.2, family = fam, fontface = "bold", colour = TH$txt, size = tsize) +
      coord_flip() + scale_y_continuous(labels = fmt_axis, limits = c(0, vmax * 1.25), expand = c(0, 0)) + theme_vid +
      theme(panel.grid.major.y = element_blank(), panel.grid.major.x = element_line(colour = TH$grid),
            axis.text.y = element_text(colour = TH$txt, size = base * 1.05)))
  }
  if (kind %in% c("line", "area")) {
    lv <- levels(df$label); L <- length(lv)
    pos <- ease(t) * (L - 1) + 1          # how far along the x axis the pen has reached
    parts <- lapply(split(df, df$group), function(x) {
      x$xi <- match(as.character(x$label), lv); x <- x[order(x$xi), ]
      full <- x[x$xi <= floor(pos), ]
      if (floor(pos) < L && nrow(full)) {
        a <- x[x$xi == floor(pos), ]; b <- x[x$xi == floor(pos) + 1, ]
        if (nrow(a) && nrow(b)) {
          f <- pos - floor(pos)
          full <- rbind(full, data.frame(label = b$label, value = a$value + (b$value - a$value) * f, group = a$group,
                                         xi = a$xi + f, stringsAsFactors = FALSE)[, names(full)])
        }
      }
      full
    })
    d <- do.call(rbind, parts)
    pts <- d[abs(d$xi - round(d$xi)) < 1e-9, ]
    pts$pop <- pmin(1, (pos - pts$xi) * 2.5 + 0.2)
    g <- ggplot(d, aes(xi, value, group = group, colour = group, fill = group))
    if (kind == "area") g <- g + geom_area(alpha = 0.28, colour = NA, position = "identity")
    dmin <- min(df$value)
    lo <- if (kind == "area") min(0, dmin) else dmin - (vmax - dmin) * 0.25
    return(g + geom_line(linewidth = 2.4) + geom_point(data = pts, aes(size = pop), show.legend = FALSE) +
      scale_size_continuous(range = c(0, base / 3), limits = c(0, 1)) +
      geom_text(data = pts[pts$pop > 0.6, ], aes(label = fmt(value)), vjust = -1.2, family = fam, fontface = "bold",
                size = tsize, show.legend = FALSE) +
      scale_x_continuous(breaks = seq_len(L), labels = lv, limits = c(0.7, L + 0.3), expand = c(0, 0)) +
      scale_y_continuous(labels = fmt_axis, limits = c(lo, vmax + (vmax - lo) * 0.18)) + colv + fillv + theme_vid +
      theme(legend.position = if (multi) "top" else "none", axis.text.x = element_text(colour = TH$txt, size = base * 1.05)))
  }
  if (kind == "stacked") {
    gs <- unique(df$group); k <- length(gs)
    d <- df; d$v <- d$value * sapply(match(d$group, gs), function(i) stag(t, i, k, 0.6))
    tot <- max(tapply(df$value, df$label, sum))
    return(ggplot(d, aes(label, v, fill = factor(group, levels = rev(gs)))) + geom_col(width = 0.62) +
      scale_fill_manual(values = rev(rep(TH$pal, 5)[seq_len(k)]), breaks = gs) +
      scale_y_continuous(labels = fmt_axis, limits = c(0, tot * 1.12), expand = c(0, 0)) + theme_vid +
      theme(axis.text.x = element_text(colour = TH$txt, size = base * 1.05)))
  }
  if (kind %in% c("donut", "pie")) {
    tot <- sum(df$value); sweep <- ease(t) * tot
    d <- df; cs <- cumsum(d$value) - d$value
    d$v <- pmax(0, pmin(d$value, sweep - cs))
    d$pct <- d$value / tot
    d$lab <- ifelse(d$v >= d$value * 0.999 & d$pct > 0.05, paste0(d2b(format(round(d$pct * 100), trim = TRUE)), "%"), "")
    d <- rbind(d, data.frame(label = "__rest", value = 0, group = "a", v = tot - sum(d$v), pct = 0, lab = "")[, names(d)])
    d$label <- factor(d$label, levels = c(levels(df$label), "__rest"))
    cols <- c(setNames(rep(TH$pal, 5)[seq_len(n)], levels(df$label)), "__rest" = "transparent")
    g <- ggplot(d, aes(x = 2, y = v, fill = label)) + geom_col(colour = NA, width = 1) +
      geom_text(aes(label = lab), position = position_stack(vjust = 0.5), family = fam, fontface = "bold",
                colour = ifelse(look == "light", "#ffffff", "#0b0c0e"), size = tsize) +
      coord_polar(theta = "y", direction = -1) + scale_fill_manual(values = cols, breaks = levels(df$label)) +
      theme_void(base_family = fam, base_size = base) +
      theme(legend.position = "right", legend.title = element_blank(), legend.text = element_text(colour = TH$txt, size = base * 1.05),
            legend.key.size = unit(base * 1.4, "pt"), plot.background = element_rect(fill = "transparent", colour = NA))
    return(if (kind == "donut") g + xlim(c(0.6, 2.5)) else g + xlim(c(1.5, 2.5)))
  }
  if (kind == "waffle") {
    tot <- if (n == 1) 100 else sum(df$value)
    cnt <- round(df$value / tot * 100)
    cats <- c(rep(as.character(df$label), cnt), rep("__rest", 100))[1:100]
    g <- expand.grid(x = 1:10, y = 10:1)
    g$cat <- factor(cats, levels = c(as.character(df$label), "__rest"))
    shown <- seq_len(100) <= ceiling(ease(t) * 100)
    g$cat[!shown & g$cat != "__rest"] <- "__rest"
    cols <- c(setNames(rep(TH$pal, 5)[seq_len(n)], as.character(df$label)), "__rest" = TH$grid)
    return(ggplot(g, aes(x, y, fill = cat)) + geom_tile(colour = NA, width = 0.82, height = 0.82) + coord_equal() +
      scale_fill_manual(values = cols, breaks = as.character(df$label), drop = FALSE) + theme_void(base_family = fam, base_size = base) +
      theme(legend.position = "right", legend.title = element_blank(), legend.text = element_text(colour = TH$txt, size = base * 1.05),
            plot.background = element_rect(fill = "transparent", colour = NA)))
  }
  if (kind == "treemap") {
    library(treemapify)
    d <- df[order(-df$value), ]
    d$a <- sapply(seq_len(nrow(d)), function(i) stag(t, i, nrow(d), 0.7))
    d$lab <- ifelse(d$a > 0.6, paste0(d$label, "\n", fmt(d$value)), "")
    return(ggplot(d, aes(area = value, fill = label, label = lab, alpha = a)) + geom_treemap(colour = "#00000055", size = 2) +
      geom_treemap_text(family = fam, colour = ifelse(look == "light", "#ffffff", "#0b0c0e"), fontface = "bold",
                        place = "centre", grow = FALSE, size = base * 1.1, reflow = TRUE) +
      scale_alpha_identity() + fillv + theme_void() +
      theme(legend.position = "none", plot.background = element_rect(fill = "transparent", colour = NA)))
  }
  # bar (default): bars rise one after another, numbers count up; grouped when several series
  k <- n
  d <- df; d$p <- sapply(seq_len(k), function(i) stag(t, i, k)); d$v <- d$value * d$p
  d$lab <- ifelse(d$p > 0.03, fmt(d$v), "")
  ggplot(d, aes(label, v, fill = if (multi) group else "x")) +
    geom_col(width = if (multi) 0.72 else 0.6, position = position_dodge(width = 0.76)) +
    geom_text(aes(label = lab), position = position_dodge(width = 0.76), vjust = -0.45, family = fam, fontface = "bold",
              colour = TH$txt, size = tsize * (if (multi) 0.8 else 1)) +
    (if (multi) fillv else scale_fill_manual(values = TH$acc)) +
    scale_y_continuous(labels = fmt_axis, limits = c(min(0, vmin), vmax * 1.18), expand = c(0, 0)) + theme_vid +
    theme(legend.position = if (multi) "top" else "none", axis.text.x = element_text(colour = TH$txt, size = base * 1.05))
}

for (f in 0:(NF - 1)) {
  agg_png(file.path(outdir, sprintf("f%03d.png", f)), width = W, height = H, units = "px", res = 96, background = "transparent")
  print(frame_plot(f / (NF - 1)))
  invisible(dev.off())
}
cat("ok", NF, "\n")