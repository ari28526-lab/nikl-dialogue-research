# Revision resolution and SHA are shared with Python; R independently reopens
# the selected native JSON and checks IDs, original values and context selection.
# Args: python package links corpus utterance_id radius revision output
a <- commandArgs(trailingOnly = TRUE)
stopifnot(length(a) == 8L)
script_arg <- grep('^--file=', commandArgs(), value = TRUE)[[1]]
script <- normalizePath(sub('^--file=', '', script_arg), winslash = '/')
query <- file.path(dirname(dirname(script)), 'python', 'query_delivery_links.py')
tmp <- tempfile(fileext = '.json')
cmd <- c(query, '--package', a[[2]], '--links', a[[3]], '--corpus', a[[4]],
         '--utterance-id', a[[5]], '--radius', a[[6]], '--revision', a[[7]], '--output', tmp)
status <- system2(a[[1]], vapply(cmd, shQuote, character(1)))
stopifnot(status == 0L)
x <- jsonlite::fromJSON(tmp, simplifyVector = FALSE)
root <- normalizePath(a[[2]], winslash = '/', mustWork = TRUE)
p <- normalizePath(file.path(root, x$resolved_source_discourse), winslash = '/', mustWork = TRUE)
stopifnot(startsWith(tolower(p), paste0(tolower(root), '/')))
native <- jsonlite::fromJSON(p, simplifyVector = FALSE)
ids <- vapply(native$utterances, function(y) y$utterance_id, character(1))
target <- which(ids == a[[5]]); radius <- as.integer(a[[6]])
stopifnot(length(target) == 1L, radius >= 0L)
sel <- seq.int(max(1L, target - radius), min(length(ids), target + radius))
stopifnot(identical(native$utterances[sel], x$utterances))
stopifnot(identical(unname(ids[sel]), vapply(x$links, function(y) y$utterance_id, character(1))))
x$validation_scope <- 'Python revision resolution and changed-file SHA; independent R native JSON context/value/ID check. No full media audit.'
dir.create(dirname(a[[8]]), recursive = TRUE, showWarnings = FALSE)
jsonlite::write_json(x, a[[8]], auto_unbox = TRUE, pretty = TRUE, null = 'null', na = 'null', digits = NA)
unlink(tmp)
