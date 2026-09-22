-- Give pipe tables explicit column widths. Pandoc otherwise emits zero-width
-- colspecs for these tables; older LibreOffice versions can place later columns
-- outside the page instead of autofitting them.
function Table(tbl)
  local n = #(tbl.widths or {})
  local widths = {}
  if n == 2 then
    widths = {0.68, 0.32}
  elseif n == 3 then
    widths = {0.40, 0.30, 0.30}
  elseif n == 4 then
    widths = {0.32, 0.23, 0.23, 0.22}
  elseif n == 5 then
    widths = {0.16, 0.28, 0.20, 0.18, 0.18}
  elseif n == 7 then
    widths = {0.24, 0.10, 0.10, 0.11, 0.11, 0.15, 0.19}
  else
    for i = 1, n do
      widths[i] = 1.0 / n
    end
  end

  tbl.widths = widths
  return tbl
end
