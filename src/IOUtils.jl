module IOUtils

using JSON3

export atomic_write, atomic_write_json

# Write `content` to `path` via a temporary sibling file and an atomic rename, so an
# interrupted write can never leave a truncated artifact in the destination directory.
function atomic_write(path, content::AbstractString; mode = 0o644)
    directory = dirname(abspath(path))
    mkpath(directory)
    temporary, io = mktemp(directory)
    try
        write(io, content)
        close(io)
        chmod(temporary, mode)
        mv(temporary, path; force = true)
    catch
        isopen(io) && close(io)
        rm(temporary; force = true)
        rethrow()
    end
    return path
end

atomic_write_json(path, payload) = atomic_write(path, string(JSON3.write(payload), "\n"))

end
