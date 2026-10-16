module IOUtils

using JSON3

export atomic_write, atomic_write_json, with_work_directory

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

# Run `f(path)` with a temporary working directory (staging or backup) for `target_dir`.
# Prefer a sibling of the target so moves and rollback renames stay on one filesystem, but fall
# back to the system temporary directory when that parent is not writable (for example a mounted
# volume root such as `/data`, where the container user cannot create siblings under `/`).
function with_work_directory(f, target_dir)
    path = try
        mktempdir(dirname(abspath(target_dir)))
    catch
        # Only directory creation is attempted here, so nothing is retried or double-executed.
        mktempdir()
    end
    try
        return f(path)
    finally
        rm(path; recursive = true, force = true)
    end
end

end
