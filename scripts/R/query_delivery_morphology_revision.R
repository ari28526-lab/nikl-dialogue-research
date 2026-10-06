# Args: Arrow Python, package, base mirror, revision, result JSON, Arrow R library.
a <- commandArgs(trailingOnly=TRUE)
if(length(a)!=6L) stop('Expected 6 arguments')
.libPaths(c(a[[6]],.libPaths()))
script <- normalizePath(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[[1]]),winslash='/')
resolver <- file.path(dirname(script),'export_delivery_morphology_selection.py')
if(!file.exists(resolver)) resolver <- file.path(dirname(dirname(script)),'python','export_delivery_morphology_selection.py')
tmp <- tempfile(fileext='.json')
export_plan <- function(out) {
  status <- system2(a[[1]],vapply(c('-B',resolver,'--package',a[[2]],'--base',a[[3]],'--revision',a[[4]],'--output',out),shQuote,character(1)))
  if(status!=0L) stop('Revision routing validation failed')
  jsonlite::fromJSON(out,simplifyVector=FALSE)
}
plan <- export_plan(tmp)
root <- normalizePath(a[[2]],winslash='/',mustWork=TRUE)
safe <- function(rel) {
  p <- normalizePath(file.path(root,rel),winslash='/',mustWork=TRUE)
  if(!startsWith(tolower(p),paste0(tolower(root),'/'))) stop('Path escapes package')
  p
}
columns <- c('_source_csv','_source_row_index','utt_id','token_index','morph_index','pos','_corpus','_year')
counts <- numeric();selected <- character();total <- 0
consume <- function(x) {
  total <<- total+nrow(x)
  current <- table(x$pos)
  for(n in names(current)) {
    if(!n %in% names(counts)) counts[[n]] <<- 0
    counts[[n]] <<- counts[[n]]+as.numeric(current[[n]])
  }
  if(length(selected)<50L) {
    rows <- head(which(x$pos=='NNG'),50L-length(selected))
    if(length(rows)) selected <<- c(selected,do.call(paste,c(lapply(x[rows,columns[1:5],drop=FALSE],as.character),sep='|')))
  }
}
emitted <- rep(FALSE,length(plan$shards))
replacement <- function(i) {
  x <- as.data.frame(arrow::read_parquet(safe(plan$shards[[i]]$path),col_select=tidyselect::all_of(columns)))
  consume(x);emitted[[i]] <<- TRUE
}
for(path in plan$base_files) {
  x <- as.data.frame(arrow::read_parquet(safe(path),col_select=tidyselect::all_of(columns)))
  # Consecutive runs preserve physical base order and replacement placement.
  if(!nrow(x)) next
  match_index <- integer(nrow(x))
  for(i in seq_along(plan$shards)) {
    s <- plan$shards[[i]]
    match_index[x$`_corpus`==s$corpus & x$`_year`==s$year & x$`_source_csv`==s$source_csv] <- i
  }
  runs <- rle(match_index);end <- cumsum(runs$lengths);start <- end-runs$lengths+1L
  for(j in seq_along(runs$values)) {
    i <- runs$values[[j]]
    if(i==0L) consume(x[seq.int(start[[j]],end[[j]]),,drop=FALSE])
    else if(!emitted[[i]]) replacement(i)
  }
}
if(length(plan$shards)) {
  keys <- vapply(plan$shards,function(s) paste(s$corpus,s$year,s$source_csv,sep='|'),character(1))
  for(i in order(keys)) if(!emitted[[i]]) replacement(i)
}
again <- export_plan(tmp)
if(!identical(plan,again)) stop('Revision routing changed during R query')
result <- list(version='bareun_3.2',selected_revision=a[[4]],pos='NNG',files=length(plan$base_files),rows=total,
  counts=as.list(counts[order(names(counts))]),selected_keys=unname(selected),human_verified=FALSE,
  validation_scope='Shared Python revision/SHA routing; independent R Arrow aggregation over selected base and replacement tables.',delivery_complete=FALSE)
dir.create(dirname(a[[5]]),recursive=TRUE,showWarnings=FALSE)
jsonlite::write_json(result,a[[5]],pretty=TRUE,auto_unbox=TRUE,null='null',digits=NA)
unlink(tmp)
