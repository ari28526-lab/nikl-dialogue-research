# Read a document's portable links and native utterances without a fixed drive.
# Args: package_root links_root link_document_relative utterance_id radius output_json
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 6L)
package_root <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
links_root <- normalizePath(args[[2]], winslash = "/", mustWork = TRUE)
radius <- as.integer(args[[5]])
stopifnot(!is.na(radius), radius >= 0L)
safe_path <- function(root, rel) {
  stopifnot(length(rel) == 1L, nzchar(rel), !grepl("^/|:|\\\\", rel),
            !any(strsplit(rel, "/", fixed = TRUE)[[1]] == ".."))
  p <- normalizePath(file.path(root, rel), winslash = "/", mustWork = TRUE)
  stopifnot(startsWith(tolower(p), paste0(tolower(root), "/")))
  p
}
read_json <- function(path, compressed = FALSE) {
  con <- if (compressed) gzfile(path, "rt", encoding = "UTF-8") else file(path, "rt", encoding = "UTF-8")
  on.exit(close(con))
  jsonlite::fromJSON(paste(readLines(con, warn = FALSE), collapse = "\n"), simplifyVector = FALSE)
}
links <- read_json(safe_path(links_root, args[[3]]), TRUE)
native <- read_json(safe_path(package_root, links$source_discourse$path))
ids <- vapply(links$utterances, function(x) x$utterance_id, character(1))
native_ids <- vapply(native$utterances, function(x) x$utterance_id, character(1))
stopifnot(identical(ids, native_ids))
target <- which(ids == args[[4]])
stopifnot(length(target) == 1L)
selection <- seq.int(max(1L, target - radius), min(length(ids), target + radius))
check_refs <- function(x) {
  if (!is.list(x)) return(invisible(NULL))
  if (all(c("path", "bytes", "sha256") %in% names(x))) {
    p <- safe_path(package_root, x$path)
    stopifnot(file.info(p)$size == x$bytes)
  } else for (y in x) check_refs(y)
  invisible(NULL)
}
check_refs(links$references)
check_refs(links$utterances[selection])
result <- list(corpus = links$corpus, discourse_id = links$discourse_id,
               target_utterance_id = args[[4]], utterance_ids = unname(ids[selection]),
               utterances = native$utterances[selection], links = links$utterances[selection],
               references = links$references, references_base = "package_root",
               time_policy = links$time_policy, human_verified = FALSE,
               validation_scope = "Native/link IDs and referenced file existence/size; use Python --verify-hashes for SHA validation")
dir.create(dirname(args[[6]]), recursive = TRUE, showWarnings = FALSE)
jsonlite::write_json(result, args[[6]], auto_unbox = TRUE, pretty = TRUE, null = "null", na = "null", digits = NA)
